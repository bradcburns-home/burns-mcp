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

## Features

### 1. Gemini-compatible tool schemas

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

### 2. Three-layer errors

Standard Burns Lab three-layer error envelope serving humans, LLMs, and diagnostics:

```python
from burns_mcp import format_three_layer_error, format_three_layer_error_json

# Dict return:
err_dict = format_three_layer_error(
    error="Target date cannot be in the past.",
    next_action="Provide a future date in YYYY-MM-DD format.",
    retryable=False,
    error_type="ValidationError",
)

# JSON string return for MCP tool results:
err_json = format_three_layer_error_json(
    error="Could not connect to database.",
    next_action="Retry the operation after verifying database connectivity.",
    retryable=True,
    exc=db_exception,
)
```

Diagnostic details automatically sanitize database passwords, URIs, bearer tokens, and credentials.

### 3. Author resolution

Authenticates and canonicalizes write authors against the Burns Lab agent registry:

```python
from burns_mcp import load_registered_agent_slugs, resolve_author

slugs, loaded = load_registered_agent_slugs("/app/agents")
author, err = resolve_author("savoy", slugs, registry_loaded=loaded)
# author == "agent:savoy"
```
Special principals `cursor` (`agent:cursor`) and `brad` (`human:brad`) are permitted without an `agent.yaml`.
Fails closed when the agent directory cannot be loaded.
