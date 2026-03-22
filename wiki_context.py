"""
Persistent wiki tool server for the Clash Royale wiki MCP.
Keeps a single subprocess alive to avoid 5-10 s startup overhead per tool call.
"""

from __future__ import annotations

import json
import subprocess
import threading

WIKI_PROJECT = "/Users/colbyking/source/clash-royale-wiki-mcp"

# Runs inside the subprocess: reads JSON requests, calls tool impls, returns results
_SERVER_SCRIPT = """\
import sys, json
from cr_wiki_mcp.server.tools import (
    get_card_info_impl, get_card_counters_impl,
    get_card_synergies_impl, search_deck_strategies_impl,
    get_game_mechanics_impl, search_wiki_impl,
)
TOOLS = {
    "search_wiki":           search_wiki_impl,
    "get_card_info":         get_card_info_impl,
    "get_card_counters":     get_card_counters_impl,
    "get_card_synergies":    get_card_synergies_impl,
    "search_deck_strategies": search_deck_strategies_impl,
    "get_game_mechanics":    get_game_mechanics_impl,
}
sys.stderr.write("wiki_server ready\\n")
sys.stderr.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        fn  = TOOLS.get(req["tool"])
        result = fn(**req.get("args", {})) if fn else f"Unknown tool: {req['tool']}"
    except Exception as e:
        result = f"Error: {e}"
    print(json.dumps(result), flush=True)
"""


class _WikiServer:
    """Single persistent subprocess; thread-safe via a lock."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def _start(self):
        self._proc = subprocess.Popen(
            ["uv", "run", "--project", WIKI_PROJECT, "python", "-c", _SERVER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WIKI_PROJECT,
        )

    def call(self, tool: str, args: dict) -> str:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            try:
                self._proc.stdin.write(json.dumps({"tool": tool, "args": args}) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                return json.loads(line) if line else ""
            except Exception as e:
                print(f"[wiki_server] call failed: {e}", flush=True)
                self._proc = None
                return f"Tool call failed: {e}"


_server = _WikiServer()


def call_tool(tool: str, **args) -> str:
    """Call a wiki tool on the persistent subprocess server."""
    return _server.call(tool, args)


def dispatch_tool(name: str, tool_input: dict) -> str:
    """Dispatch an Anthropic tool_use block to the wiki server."""
    return call_tool(name, **tool_input)


# ── Anthropic tool definitions ──────────────────────────────────────────────

WIKI_TOOLS = [
    {
        "name": "search_wiki",
        "description": (
            "General semantic search across all Clash Royale wiki content. "
            "Use for broad questions or when other tools don't apply."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "doc_type": {
                    "type": "string",
                    "enum": ["all", "card", "deck", "mechanic"],
                    "description": "Optional filter by document type",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_card_info",
        "description": "Get stats, description, and details for a specific Clash Royale card.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_name": {"type": "string", "description": "Card name, e.g. 'Hog Rider'"},
            },
            "required": ["card_name"],
        },
    },
    {
        "name": "get_card_counters",
        "description": "Get cards that counter a specific card.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_name": {"type": "string", "description": "Card to find counters for"},
            },
            "required": ["card_name"],
        },
    },
    {
        "name": "get_card_synergies",
        "description": "Get cards that synergize well with a specific card.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_name": {"type": "string", "description": "Card to find synergies for"},
            },
            "required": ["card_name"],
        },
    },
    {
        "name": "search_deck_strategies",
        "description": "Search for deck compositions, archetypes, and play strategies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Strategy or archetype query"},
                "archetype": {
                    "type": "string",
                    "description": "Optional archetype filter (e.g. 'cycle', 'beatdown')",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_game_mechanics",
        "description": (
            "Get information about Clash Royale game mechanics "
            "(elixir, towers, arenas, deck building rules, etc)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Mechanic topic, e.g. 'elixir cycle', 'tower HP'",
                },
            },
            "required": ["topic"],
        },
    },
]
