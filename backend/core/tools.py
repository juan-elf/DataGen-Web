"""
Tool definitions for the DataGen agent.

4 tools:
- execute_sql: query the workspace's data (primary)
- get_distinct_values: inspect unique values in a column
- run_analysis: sandboxed pandas analysis
- web_search: search external information (Tavily)

Ported from DataGen (universal-sql-agent/tools.py); only import paths changed.
"""
import json

from core.database import execute_query, get_distinct_values
from core.web_search import search_web
from core.analysis import run_analysis as _run_analysis_fn


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a SELECT SQL query against the workspace's data. "
                "USE THIS FIRST for any question about data in the workspace. "
                "Only SELECT/WITH is allowed (read-only). "
                "The response includes a 'hint' field to help fix query errors."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT SQL query. PostgreSQL syntax."
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_distinct_values",
            "description": (
                "Get unique values from a categorical column. "
                "Use BEFORE filtering with WHERE when unsure what values exist "
                "in a column (prevents hallucinated filter values)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "column": {"type": "string", "description": "Column name"},
                    "limit": {"type": "integer", "description": "Max values to return (default 20)"}
                },
                "required": ["table", "column"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_analysis",
            "description": (
                "Execute Python/pandas code on the result of a SQL query. "
                "USE FOR analysis that is hard or impossible in SQL: "
                "correlation, z-score anomaly detection, statistical distribution, "
                "linear trend, percentile breakdown. "
                "DO NOT use for simple aggregation — execute_sql is faster for that. "
                "The code runs on a DataFrame named `df` (from the SQL result). "
                "Available: pd (pandas), np (numpy), stats (scipy.stats if installed). "
                "Code MUST assign output to `result`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT query whose result becomes DataFrame `df`."
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "Python code that analyzes `df` and assigns to `result`. "
                            "Example: result = {'corr': float(df['x'].corr(df['y'])), "
                            "'mean_y': float(df['y'].mean())}"
                        )
                    }
                },
                "required": ["sql", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for information. USE THIS ONLY WHEN: "
                "(a) the data is NOT in the workspace (confirmed via execute_sql), OR "
                "(b) the user needs external context like industry benchmarks, "
                "concept definitions, typical/normal values, or standards. "
                "NEVER use web_search for data that exists in the workspace — "
                "always try the database first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in English for best results."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results (default 5, max 10)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def _run_analysis_tool(sql: str, code: str) -> str:
    result = _run_analysis_fn(sql, code)
    return json.dumps(result, ensure_ascii=False, default=str)


def _execute_sql_tool(sql: str) -> str:
    result = execute_query(sql)
    if result["success"] and result["row_count"] > 50:
        result = {
            **result,
            "rows": result["rows"][:50],
            "note": (
                f"Total {result['row_count']} rows, showing first 50. "
                f"Consider using aggregation (AVG/MIN/MAX/COUNT) for large datasets."
            )
        }
    return json.dumps(result, ensure_ascii=False, default=str)


def _get_distinct_values_tool(table: str, column: str, limit: int = 20) -> str:
    result = get_distinct_values(table, column, limit)
    return json.dumps(result, ensure_ascii=False, default=str)


def _web_search_tool(query: str, max_results: int = 5) -> str:
    result = search_web(query, max_results)
    return json.dumps(result, ensure_ascii=False, default=str)


TOOL_FUNCTIONS = {
    "execute_sql": _execute_sql_tool,
    "get_distinct_values": _get_distinct_values_tool,
    "web_search": _web_search_tool,
    "run_analysis": _run_analysis_tool,
}


def call_tool(tool_name: str, arguments: dict) -> str:
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        })

    try:
        return TOOL_FUNCTIONS[tool_name](**arguments)
    except TypeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid arguments for tool '{tool_name}': {e}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Tool '{tool_name}' error: {type(e).__name__}: {e}"
        })
