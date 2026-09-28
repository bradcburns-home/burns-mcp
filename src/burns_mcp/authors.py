"""Author identity resolution and verification across Burns Lab MCP tools.

Enforces that tool mutations are attributed to a known registered agent
or recognized human operator. Normalizes author strings to canonical formats:
- Registered agent: ``agent:<name>`` (e.g. ``agent:savoy``, ``agent:cursor``)
- Human operator: ``human:brad``

Fails closed when the agent registry cannot be loaded.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from burns_mcp.errors import format_three_layer_error

logger = logging.getLogger(__name__)

# Special built-in principals permitted without agent.yaml registration
SPECIAL_PRINCIPALS: dict[str, str] = {
    "cursor": "agent:cursor",
    "agent:cursor": "agent:cursor",
    "brad": "human:brad",
    "human:brad": "human:brad",
}


def load_registered_agent_slugs(agents_dir: str | Path) -> tuple[set[str], bool]:
    """Scan agents_dir/*/agent.yaml for top-level `name:` definitions.

    Returns:
        (set of lowercase slug strings, registry_loaded boolean).
    """
    root = Path(agents_dir)
    if not root.is_dir():
        logger.warning("Agent registry directory not found or not a directory: %s", agents_dir)
        return set(), False

    slugs: set[str] = set()
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        yaml_path = sub / "agent.yaml"
        if not yaml_path.is_file():
            continue
        try:
            name = _read_agent_yaml_name(yaml_path)
            if name:
                slugs.add(name.strip().lower())
        except OSError as e:
            logger.warning("Could not read %s: %s", yaml_path, e)

    if not slugs:
        logger.warning("No agent names could be loaded from %s", agents_dir)
        return set(), False

    logger.info("Loaded %d registered agent slug(s) from %s: %s", len(slugs), root, sorted(slugs))
    return slugs, True


def _read_agent_yaml_name(path: Path) -> str | None:
    """Extract `name:` value from agent.yaml without requiring PyYAML."""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            val = stripped.split(":", 1)[1].strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                return val[1:-1]
            return val
    return None


def resolve_author(
    author: str,
    registered_slugs: set[str],
    registry_loaded: bool,
    *,
    fail_closed: bool = True,
) -> tuple[str | None, dict[str, Any] | None]:
    """Normalize author to canonical stored form (agent:slug or human:brad).

    Returns:
        (canonical_author, None) on success, or (None, three_layer_error_dict) on failure.
    """
    s = (author or "").strip()
    if not s:
        err = format_three_layer_error(
            error="author parameter is required.",
            next_action="Provide your registered agent slug (e.g. 'savoy' or 'cursor') or 'brad'.",
            error_type="AuthorRequiredError",
        )
        return None, err

    lower = s.lower()

    # 1. Check special built-in principals
    if lower in SPECIAL_PRINCIPALS:
        return SPECIAL_PRINCIPALS[lower], None

    # 2. If registry failed to load, fail closed
    if not registry_loaded:
        if fail_closed:
            err = format_three_layer_error(
                error="Agent registry is unavailable; author validation cannot proceed.",
                next_action="Ensure the /app/agents volume is mounted and healthy before executing writes.",
                error_type="RegistryUnavailableError",
                retryable=True,
            )
            return None, err
        logger.warning("Degraded author validation: accepting author '%s' without registry verification", s)
        if lower.startswith("agent:") or lower.startswith("human:"):
            return lower, None
        return f"agent:{lower}", None

    # 3. Canonicalize prefixed agent string
    if lower.startswith("agent:"):
        slug = lower.split(":", 1)[1].strip()
        if slug in registered_slugs:
            return f"agent:{slug}", None
        valid_list = sorted(list(registered_slugs) + ["cursor", "brad"])
        err = format_three_layer_error(
            error=f"Unknown agent author '{s}'.",
            next_action=f"Specify one of the registered authors: {', '.join(valid_list)}.",
            error_type="UnknownAuthorError",
        )
        return None, err

    # 4. Bare slug check
    if lower in registered_slugs:
        return f"agent:{lower}", None

    valid_list = sorted(list(registered_slugs) + ["cursor", "brad"])
    err = format_three_layer_error(
        error=f"Unrecognized author '{author}'.",
        next_action=f"Pass a valid registered agent name or 'brad'. Allowed: {', '.join(valid_list)}.",
        error_type="UnknownAuthorError",
    )
    return None, err
