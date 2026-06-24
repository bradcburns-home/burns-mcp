# burns-mcp

Shared scaffolding for Burns Lab FastMCP servers — the single home for the
boilerplate that is otherwise copy-pasted across every MCP endpoint.

Installed the same way as `burns-logger` / `burns-config`: from GitHub at build
time, e.g.

```dockerfile
RUN --mount=type=secret,id=github_token \
    . .venv/bin/activate && \
    GIT_AUTH="$(cat /run/secrets/github_token)" && \
    uv pip install "burns-mcp @ git+https://${GIT_AUTH}@github.com/bradcburns-home/burns-mcp@main"
```

## What's here today

### Gemini-compatible tool schemas

Gemini's function-calling schema converter rejects union types (`anyOf` /
`oneOf`). Pydantic emits those for every optional `X | None` tool parameter, so
any FastMCP tool with an optional argument breaks Gemini. Flatten the advertised
schemas once, after all tools are registered:

```python
from mcp.server.fastmcp import FastMCP
from burns_mcp import make_tools_gemini_compatible

mcp = FastMCP("My Server")

# ... @mcp.tool() definitions ...

make_tools_gemini_compatible(mcp)  # collapses unions in the advertised schema

app = mcp.streamable_http_app()
```

This only rewrites the *advertised* `inputSchema`. Runtime argument validation
is unchanged — FastMCP validates against the Pydantic arg model, not this
schema — so the server keeps accepting exactly what it did before.

## Planned

Migrate the rest of the per-server boilerplate into this package:

- `asgi` — `ASGICrashGuard`
- `errors` — `three_layer_error` and friends
- `author` — `resolve_author`, `load_registered_agent_slugs`
- `health` — the `/health` route helper

(Runtime LLM model-fallback handling is tracked separately; it belongs with
`burns_config`, which already owns model-tier resolution.)
