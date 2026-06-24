"""Gemini-safe JSON-schema helpers for FastMCP tool definitions.

Gemini's function-calling schema converter (for example, LibreChat's
``zod_to_gemini_parameters``) rejects union types — ``anyOf`` / ``oneOf``.
Pydantic renders every optional ``X | None`` parameter as ``anyOf: [X, null]``
(and ``str | int | None`` as a three-way union), so any FastMCP tool with an
optional parameter advertises a schema Gemini cannot ingest, which hard-fails
the whole request.

``make_tools_gemini_compatible`` rewrites each tool's *advertised* input schema
to drop those unions. It deliberately does NOT touch runtime validation:
FastMCP validates arguments against the Pydantic arg model, not the advertised
schema, so the server keeps accepting exactly what it did before — the change
is purely on the wire.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["flatten_union_schema", "make_tools_gemini_compatible"]


def flatten_union_schema(node: Any) -> Any:
    """Return a copy of a JSON schema with all union types collapsed.

    Each ``anyOf`` / ``oneOf`` is reduced to its first non-null member, whose
    keys are lifted up; sibling metadata (``description``, ``title``, ...) is
    preserved. ``type: [..., "null"]`` arrays collapse to the first non-null
    entry, and ``null``-valued defaults are dropped — an absent optional already
    means "unset", and a null default can round-trip back into a nullable union
    in a downstream JSON-schema → Zod conversion.
    """
    if isinstance(node, list):
        return [flatten_union_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    schema = {key: flatten_union_schema(value) for key, value in node.items()}

    union = schema.pop("anyOf", None)
    if union is None:
        union = schema.pop("oneOf", None)
    if isinstance(union, list):
        members = [m for m in union if not (isinstance(m, dict) and m.get("type") == "null")]
        chosen = members[0] if members else {"type": "string"}
        if isinstance(chosen, dict):
            # The member supplies type/constraints; existing siblings win on
            # metadata so descriptions/titles/defaults survive.
            schema = {**chosen, **schema}

    declared_type = schema.get("type")
    if isinstance(declared_type, list):
        non_null = [t for t in declared_type if t != "null"]
        schema["type"] = non_null[0] if non_null else "string"

    if "default" in schema and schema["default"] is None:
        del schema["default"]

    return schema


def make_tools_gemini_compatible(server: Any) -> list[str]:
    """Flatten union types in every advertised tool schema of a FastMCP server.

    Mutates each registered tool's ``parameters`` (the wire-facing
    ``inputSchema``) in place and returns the names of the tools that changed.

    Call once, after all tools are registered (i.e. after the ``@mcp.tool()``
    definitions). Defensive against FastMCP internals: any failure degrades to a
    logged warning rather than crashing server startup, since advertising must
    never take the server down.
    """
    changed: list[str] = []
    try:
        tools = server._tool_manager.list_tools()
    except Exception:  # pragma: no cover - defensive against FastMCP internals
        logger.exception("burns_mcp: could not enumerate tools for Gemini schema flattening")
        return changed

    for tool in tools:
        name = getattr(tool, "name", "?")
        try:
            original = tool.parameters
            flattened = flatten_union_schema(original)
            if flattened != original:
                tool.parameters = flattened
                changed.append(name)
        except Exception:  # pragma: no cover - advertising must never break startup
            logger.exception("burns_mcp: failed to flatten schema for tool %s", name)

    if changed:
        logger.info("burns_mcp: flattened union types in %d tool schema(s): %s", len(changed), ", ".join(changed))
    return changed
