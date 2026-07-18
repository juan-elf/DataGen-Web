"""
Agent loop — DataGen web backend.

System prompt is built in layers: generic instructions + schema + optional
domain pack. Domain packs are loaded from backend/domains/*.md.

Ported from DataGen (universal-sql-agent/agent.py) with two structural changes
for the web backend:
  1. No `ui` (rich CLI) dependency — `chat_stream()` yields structured event
     dicts instead of printing, so `api/chat.py` can forward them as SSE.
  2. Postgres-only dialect (the web backend never talks to SQLite).
Everything else — the tool loop, retry/backoff, guardrail call sites — is
the same shape as the CLI agent.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from dotenv import load_dotenv

from core.database import get_schema, get_db_label
from core.tools import TOOLS_SCHEMA, call_tool
from core.logger import ConversationLogger
from core.web_search import is_available as web_available
from core.profiler import profile_database, format_profile_for_prompt
from core.guardrails import harden_system_prompt, check_input_with_llm

load_dotenv()

MODEL_NAME = os.getenv("AGENT_MODEL", "google/gemma-4-31b-it:free")
GUARDRAIL_MODEL = os.getenv("GUARDRAIL_MODEL", "openai/gpt-oss-120b:free")
MAX_ITERATIONS = 10
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

DOMAINS_DIR = Path(__file__).resolve().parent.parent / "domains"

_openrouter_base = "https://openrouter.ai/api/v1"

# Fall back to a placeholder key instead of letting the SDK raise at import
# time: the backend (health checks, /upload) must stay importable even before
# OPENROUTER_API_KEY is configured on a fresh deploy. A missing/placeholder
# key just makes actual chat calls fail per-request (caught by
# _call_api_with_retry below), which is the right failure mode here.
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY") or "sk-not-configured",
    base_url=_openrouter_base,
)

guardrail_client = OpenAI(
    api_key=os.getenv("GUARDRAIL_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "sk-not-configured",
    base_url=_openrouter_base,
)


def list_available_domains() -> list[str]:
    """List domain pack names available in backend/domains/."""
    if not DOMAINS_DIR.exists():
        return []
    return sorted([p.stem for p in DOMAINS_DIR.glob("*.md")])


def load_domain_pack(name: str) -> str | None:
    """Load a domain pack by name (without .md extension). Returns None if not found."""
    pack_path = DOMAINS_DIR / f"{name}.md"
    if not pack_path.exists():
        return None
    return pack_path.read_text(encoding="utf-8")


GENERIC_INSTRUCTIONS = """You are DataGen — help users answer questions about \
their uploaded data using natural language.

How you work:
1. Understand the user's question and inspect the workspace schema
2. Generate the appropriate SELECT SQL query
3. Execute it via the execute_sql tool
4. Format the result into a natural, informative answer

═══════════════════════════════════════════════════════════════
AVAILABLE TOOLS:
═══════════════════════════════════════════════════════════════
- execute_sql: run a SELECT query (primary tool for all data questions)
- get_distinct_values: check unique values in a categorical column
- run_analysis: execute Python/pandas code on SQL results — USE FOR analysis \
that is hard in SQL: correlation, z-score anomaly detection, distribution stats, \
linear trend. NOT for simple aggregation (use execute_sql instead).
- web_search: search external info — use ONLY when (a) data is not in the workspace, \
OR (b) external context is needed (definitions, benchmarks, industry standards)

═══════════════════════════════════════════════════════════════
SOURCE PRIORITY STRATEGY:
═══════════════════════════════════════════════════════════════
1. Workspace data FIRST for questions about the user's uploaded data
2. Web search ONLY when:
   a) Data is not in the workspace (confirmed via SQL), OR
   b) User requests benchmarks, definitions, or external context
3. COMBINE workspace data + web when both are needed
   (e.g. "is our value X normal?")
   When combining, label which data comes from the workspace vs. the web.

═══════════════════════════════════════════════════════════════
GENERAL RULES:
═══════════════════════════════════════════════════════════════
1. For JOINs, use the foreign keys shown in the schema.
2. SELECT only the columns the question asks for. For ranking / top-N /
   "which X has the highest/lowest Y" questions, return just the identifying
   column and the metric being ranked — do NOT add extra context columns
   unless the user explicitly asks for them.
3. If a query errors, READ the 'hint' field in the response and fix it.
   NEVER retry the exact same failing query.
4. If unsure about values in a categorical column, use get_distinct_values first.
5. If the question is ambiguous, ask for clarification before querying.
6. Reply in natural, informative Bahasa Indonesia.
7. Use markdown formatting in answers (bold, lists, tables).
8. Include UNITS on numeric results where relevant (Rp, °C, %, kg, etc.).
"""

_DIALECT_RULES = (
    "═══════════════════════════════════════════════════════════════\n"
    "SQL DIALECT: PostgreSQL (Supabase)\n"
    "═══════════════════════════════════════════════════════════════\n"
    "- Monthly grouping: to_char(date_col, 'YYYY-MM') "
    "or DATE_TRUNC('month', date_col)\n"
    "- Dates stored as DATE or TIMESTAMP\n"
    "- String concat: || operator or CONCAT()\n"
    "- Case-insensitive match: ILIKE\n"
    "- Type casting: value::text, value::integer\n"
    "- Window functions supported (LAG, LEAD, ROW_NUMBER, etc.)"
)


def build_system_prompt(domain_name: str | None = None) -> str:
    """
    Build the layered system prompt:
    1. Generic instructions + Postgres dialect rules
    2. Workspace schema (auto-detected)
    3. Data profile (row counts, ranges, cardinality — cached per workspace)
    4. Domain pack (optional)
    """
    schema = get_schema()
    db_label = get_db_label()
    web_status = "ACTIVE" if web_available() else "INACTIVE"

    try:
        profile = profile_database()
        profile_text = format_profile_for_prompt(profile)
    except Exception:
        profile_text = "(Data profile unavailable)"

    parts = [
        GENERIC_INSTRUCTIONS,
        _DIALECT_RULES,
        f"\nWEB SEARCH STATUS: {web_status}\n",
        "═══════════════════════════════════════════════════════════════",
        f"WORKSPACE: {db_label}",
        "═══════════════════════════════════════════════════════════════",
        schema,
        "\n═══════════════════════════════════════════════════════════════",
        "DATA PROFILE  (cached once — row counts, ranges, cardinality)",
        "═══════════════════════════════════════════════════════════════",
        profile_text,
    ]

    if domain_name:
        domain_content = load_domain_pack(domain_name)
        if domain_content:
            parts.extend([
                "\n═══════════════════════════════════════════════════════════════",
                f"DOMAIN KNOWLEDGE: {domain_name}",
                "═══════════════════════════════════════════════════════════════",
                domain_content,
            ])
        else:
            available = list_available_domains()
            parts.append(
                f"\n[INFO] Domain pack '{domain_name}' not found. "
                f"Available: {available or 'none'}. "
                f"Proceeding without domain knowledge."
            )

    return harden_system_prompt("\n".join(parts))


def _call_api_with_retry(messages: list, tools: list) -> Any:
    """Call the API with exponential backoff retry."""
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        except (RateLimitError, APIConnectionError, APIError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(INITIAL_BACKOFF * (2 ** attempt))
            else:
                raise
    raise last_exception


class Agent:
    """DataGen agent with optional domain specialization, request-scoped per workspace."""

    def __init__(
        self,
        domain: str | None = None,
        enable_logging: bool = True,
        workspace_id: str = "unknown",
    ):
        self.domain = domain
        self.workspace_id = workspace_id
        self.system_prompt = build_system_prompt(domain)
        self.messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        self.logger = ConversationLogger(workspace_id) if enable_logging else None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        return {
            "session_id": self.logger.session_id if self.logger else None,
            "domain": self.domain or "(none)",
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "messages_in_history": len(self.messages),
        }

    def chat_stream(self, user_message: str) -> Iterator[dict[str, Any]]:
        """
        Process one user message through the agent loop, yielding progress events:
          {"type": "blocked", "reason": ...}
          {"type": "iteration", "n": ...}
          {"type": "tool_call", "tool": ..., "arguments": ...}
          {"type": "tool_result", "tool": ..., "result": ...}
          {"type": "final", "content": ...}
          {"type": "error", "content": ...}
        The last event is always "final", "blocked", or "error".
        """
        if self.logger:
            self.logger.log_user_message(user_message)

        allow, reason = check_input_with_llm(user_message, guardrail_client, GUARDRAIL_MODEL)
        if not allow:
            if self.logger:
                self.logger.log_error("input_blocked", reason)
            yield {"type": "blocked", "reason": reason}
            return

        # Only append to history after guardrail passes — blocked messages must not
        # enter conversation context or the next LLM call will answer them anyway.
        self.messages.append({"role": "user", "content": user_message})

        for iteration in range(MAX_ITERATIONS):
            yield {"type": "iteration", "n": iteration + 1}

            try:
                response = _call_api_with_retry(self.messages, TOOLS_SCHEMA)
            except Exception as e:
                error_msg = (f"API failed after {MAX_RETRIES} retries: "
                             f"{type(e).__name__}: {e}")
                if self.logger:
                    self.logger.log_error("api_failure", error_msg)
                yield {"type": "error", "content": f"⚠️ {error_msg}. Please try again later."}
                return

            if response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens

            assistant_msg = response.choices[0].message

            if assistant_msg.tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_msg.tool_calls
                    ]
                })

                for tool_call in assistant_msg.tool_calls:
                    tool_name = tool_call.function.name

                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        error_result = json.dumps({
                            "success": False,
                            "error": f"Invalid tool arguments (not valid JSON): {e}"
                        })
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_result
                        })
                        continue

                    yield {"type": "tool_call", "tool": tool_name, "arguments": tool_args}

                    result = call_tool(tool_name, tool_args)

                    yield {"type": "tool_result", "tool": tool_name, "result": result}

                    if self.logger:
                        self.logger.log_tool_call(tool_name, tool_args, result)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })

                continue

            final_answer = assistant_msg.content
            self.messages.append({"role": "assistant", "content": final_answer})

            if self.logger:
                self.logger.log_assistant_message(
                    final_answer,
                    token_usage={
                        "total_input": self.total_input_tokens,
                        "total_output": self.total_output_tokens,
                    }
                )
            yield {"type": "final", "content": final_answer}
            return

        msg = "⚠️ Max iterations reached. Try a more specific question."
        if self.logger:
            self.logger.log_error("max_iterations", msg)
        yield {"type": "error", "content": msg}

    def chat(self, user_message: str) -> str:
        """Non-streaming convenience wrapper — returns only the final answer text."""
        final = ""
        for event in self.chat_stream(user_message):
            if event["type"] in ("final", "error"):
                final = event["content"]
            elif event["type"] == "blocked":
                final = f"Maaf, pesan tidak dapat diproses: {event['reason']}"
        return final

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.logger = ConversationLogger(self.workspace_id) if self.logger else None
