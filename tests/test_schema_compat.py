"""Tests for burns_mcp.schema_compat (pure-python; no FastMCP/pydantic needed)."""

from __future__ import annotations

from burns_mcp.schema_compat import flatten_union_schema, make_tools_gemini_compatible


def _has_union(node) -> bool:
    if isinstance(node, dict):
        if "anyOf" in node or "oneOf" in node:
            return True
        if isinstance(node.get("type"), list):
            return True
        return any(_has_union(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_union(i) for i in node)
    return False


class TestFlattenUnionSchema:
    def test_optional_str_drops_null_keeps_metadata(self):
        out = flatten_union_schema({
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "d",
            "title": "T",
        })
        assert out == {"type": "string", "description": "d", "title": "T"}

    def test_three_way_union_picks_first_non_null(self):
        out = flatten_union_schema({
            "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
            "default": None,
        })
        assert out == {"type": "string"}

    def test_type_list_collapses(self):
        assert flatten_union_schema({"type": ["string", "null"]}) == {"type": "string"}

    def test_oneof_handled(self):
        assert flatten_union_schema({"oneOf": [{"type": "integer"}, {"type": "null"}]}) == {"type": "integer"}

    def test_non_null_default_preserved(self):
        out = flatten_union_schema({
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "default": 50,
        })
        assert out == {"type": "integer", "default": 50}

    def test_nested_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                "b": {"type": "string"},
            },
            "required": ["b"],
        }
        out = flatten_union_schema(schema)
        assert not _has_union(out)
        assert out["properties"]["a"] == {"type": "string"}
        assert out["properties"]["b"] == {"type": "string"}
        assert out["required"] == ["b"]

    def test_idempotent(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
        once = flatten_union_schema(schema)
        assert once == flatten_union_schema(once)

    def test_scalars_and_lists_passthrough(self):
        assert flatten_union_schema("x") == "x"
        assert flatten_union_schema(5) == 5
        assert flatten_union_schema([{"type": ["integer", "null"]}]) == [{"type": "integer"}]


class _FakeTool:
    def __init__(self, name, parameters):
        self.name = name
        self.parameters = parameters


class _FakeManager:
    def __init__(self, tools):
        self._tools = tools

    def list_tools(self):
        return self._tools


class _FakeServer:
    def __init__(self, tools):
        self._tool_manager = _FakeManager(tools)


class TestMakeToolsGeminiCompatible:
    def test_flattens_and_reports_changes(self):
        t1 = _FakeTool("list_events", {
            "type": "object",
            "properties": {"q": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}},
        })
        t2 = _FakeTool("get_event", {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        })
        server = _FakeServer([t1, t2])

        changed = make_tools_gemini_compatible(server)

        assert changed == ["list_events"]
        assert not _has_union(t1.parameters)
        assert t1.parameters["properties"]["q"] == {"type": "string"}
        assert t2.parameters["properties"]["id"] == {"type": "string"}  # untouched

    def test_defensive_on_bad_server(self):
        class Broken:
            @property
            def _tool_manager(self):
                raise RuntimeError("boom")

        assert make_tools_gemini_compatible(Broken()) == []
