import pytest

from core.context import WorkspaceContext, get_context, use_context


def test_get_context_raises_when_unset():
    with pytest.raises(RuntimeError):
        get_context()


def test_use_context_sets_and_resets():
    ctx = WorkspaceContext(workspace_id="abc123", schema="workspace_abc123", dsn="postgresql://u:p@h:5432/d")
    with use_context(ctx):
        assert get_context() is ctx
        assert get_context().schema == "workspace_abc123"
    with pytest.raises(RuntimeError):
        get_context()


def test_use_context_nesting_restores_outer():
    outer = WorkspaceContext(workspace_id="outer", schema="workspace_outer", dsn="postgresql://u:p@h:5432/d")
    inner = WorkspaceContext(workspace_id="inner", schema="workspace_inner", dsn="postgresql://u:p@h:5432/d")
    with use_context(outer):
        with use_context(inner):
            assert get_context().workspace_id == "inner"
        assert get_context().workspace_id == "outer"


def test_use_context_resets_even_on_exception():
    ctx = WorkspaceContext(workspace_id="x", schema="workspace_x", dsn="postgresql://u:p@h:5432/d")
    with pytest.raises(ValueError):
        with use_context(ctx):
            raise ValueError("boom")
    with pytest.raises(RuntimeError):
        get_context()
