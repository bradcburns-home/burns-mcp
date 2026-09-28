"""burns-mcp: shared scaffolding for Burns Lab FastMCP servers.

Provides:
- Gemini-compatible tool-schema helpers (flatten_union_schema, make_tools_gemini_compatible)
- Three-layer error handling (McpServiceError, format_three_layer_error, format_three_layer_error_json)
- Author resolution & registry loading (load_registered_agent_slugs, resolve_author)
"""

from burns_mcp.authors import load_registered_agent_slugs, resolve_author
from burns_mcp.errors import (
    McpServiceError,
    format_three_layer_error,
    format_three_layer_error_json,
    sanitize_text,
)
from burns_mcp.schema_compat import flatten_union_schema, make_tools_gemini_compatible

__all__ = [
    "flatten_union_schema",
    "make_tools_gemini_compatible",
    "McpServiceError",
    "format_three_layer_error",
    "format_three_layer_error_json",
    "sanitize_text",
    "load_registered_agent_slugs",
    "resolve_author",
]
__version__ = "0.2.0"
