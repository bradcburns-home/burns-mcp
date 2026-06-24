"""burns-mcp: shared scaffolding for Burns Lab FastMCP servers.

Today this provides Gemini-compatible tool-schema helpers. It is the intended
home for the boilerplate currently copy-pasted across MCP servers (ASGI crash
guard, three-layer errors, author utilities, the ``/health`` route) so that
scaffolding lives in one place instead of N near-identical copies.

Usage:
    from burns_mcp import make_tools_gemini_compatible

    mcp = FastMCP(...)
    # ... register tools ...
    make_tools_gemini_compatible(mcp)  # after all @mcp.tool() defs
"""

from burns_mcp.schema_compat import flatten_union_schema, make_tools_gemini_compatible

__all__ = ["flatten_union_schema", "make_tools_gemini_compatible"]
__version__ = "0.1.0"
