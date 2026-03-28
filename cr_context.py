"""
Persistent Clash Royale API tool server.

Uses the same JSON-line subprocess protocol as wiki_context.py.
Gracefully disabled when neither CLASH_ROYALE_API_TOKEN nor CLASH_ROYALE_API_KEY
is set in the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading

CR_PROJECT = "/Users/colbyking/source/clash-royale-mcp"

# Runs inside the subprocess — reads JSON requests, calls CR API, returns results.
# Falls back from CLASH_ROYALE_API_TOKEN to CLASH_ROYALE_API_KEY so the app's
# existing env var works without any changes to .env.
_SERVER_SCRIPT = """\
import sys, json, asyncio, os


async def _handle(tool, args):
    from clash_royale_mcp.client import ClashRoyaleClient, ClashAPIError
    from clash_royale_mcp.utils import normalize_tag
    import httpx

    token = (
        os.environ.get("CLASH_ROYALE_API_TOKEN")
        or os.environ.get("CLASH_ROYALE_API_KEY", "")
    )
    base_url = os.environ.get(
        "CLASH_ROYALE_BASE_URL", "https://proxy.royaleapi.dev/v1"
    )

    if not token:
        return "Clash Royale API token not configured (set CLASH_ROYALE_API_TOKEN or CLASH_ROYALE_API_KEY)"

    client = ClashRoyaleClient(token=token, base_url=base_url)
    try:
        if tool == "get_player_recent_decks":
            player_tag = args.get("player_tag", "")
            max_battles = int(args.get("max_battles", 25))
            data = await client.get(
                f"/players/{normalize_tag(player_tag)}/battlelog"
            )
            battles = data if isinstance(data, list) else data.get("items", [])
            battles = battles[:max_battles]

            requested_tag = "#" + player_tag.strip().lstrip("#").upper()
            deck_map = {}
            for battle in battles:
                team = battle.get("team", [])
                player_entry = next(
                    (m for m in team if m.get("tag", "").upper() == requested_tag),
                    None,
                ) or (team[0] if team else None)
                if not player_entry:
                    continue
                cards = player_entry.get("cards", [])
                deck_key = tuple(sorted(c.get("name", "") for c in cards))
                opp = (battle.get("opponent") or [{}])[0]
                is_win = player_entry.get("crowns", 0) > opp.get("crowns", 0)
                if deck_key not in deck_map:
                    deck_map[deck_key] = {
                        "cards": [
                            {
                                "name": c.get("name"),
                                "level": c.get("level"),
                                "elixirCost": c.get("elixirCost"),
                                "rarity": c.get("rarity"),
                            }
                            for c in cards
                        ],
                        "wins": 0,
                        "losses": 0,
                        "usage_count": 0,
                        "last_used": battle.get("battleTime", ""),
                    }
                e = deck_map[deck_key]
                e["usage_count"] += 1
                if is_win:
                    e["wins"] += 1
                else:
                    e["losses"] += 1
            result = []
            for entry in sorted(
                deck_map.values(), key=lambda x: x["usage_count"], reverse=True
            ):
                entry["win_rate"] = (
                    round(entry["wins"] / entry["usage_count"], 2)
                    if entry["usage_count"]
                    else 0.0
                )
                result.append(entry)
            return result

        elif tool == "get_player_battlelog":
            player_tag = args.get("player_tag", "")
            max_battles = int(args.get("max_battles", 10))
            data = await client.get(
                f"/players/{normalize_tag(player_tag)}/battlelog"
            )
            battles = data if isinstance(data, list) else data.get("items", [])
            battles = battles[:max_battles]
            summary = []
            for b in battles:
                team = (b.get("team") or [{}])[0]
                opp = (b.get("opponent") or [{}])[0]
                summary.append(
                    {
                        "battleTime": b.get("battleTime"),
                        "gameMode": b.get("gameMode", {}).get("name"),
                        "result": "win"
                        if team.get("crowns", 0) > opp.get("crowns", 0)
                        else "loss",
                        "team_cards": [c.get("name") for c in team.get("cards", [])],
                        "opponent_cards": [
                            c.get("name") for c in opp.get("cards", [])
                        ],
                    }
                )
            return summary

        else:
            return f"Unknown CR tool: {tool}"

    except ClashAPIError as e:
        if e.status == 403:
            return (
                "Forbidden (403): Invalid or expired API token, or IP not whitelisted. "
                "Consider using the RoyaleAPI proxy: set "
                "CLASH_ROYALE_BASE_URL=https://proxy.royaleapi.dev/v1"
            )
        if e.status == 404:
            return f"Not found (404): Player tag not found — check the tag format"
        if e.status == 429:
            return "Rate limited (429): Too many requests — try again shortly"
        if e.status == 503:
            return "Service unavailable (503): Clash Royale API is in maintenance"
        return f"API error ({e.status}): {e.reason} — {e.message}"
    except httpx.TimeoutException:
        return "Request timed out — Clash Royale API did not respond in time"
    except Exception as ex:
        return f"Error: {ex}"
    finally:
        await client.close()


sys.stderr.write("cr_server ready\\n")
sys.stderr.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        result = asyncio.run(_handle(req.get("tool", ""), req.get("args", {})))
    except Exception as ex:
        result = f"Error: {ex}"
    print(json.dumps(result), flush=True)
"""


def _token_available() -> bool:
    return bool(
        os.environ.get("CLASH_ROYALE_API_TOKEN")
        or os.environ.get("CLASH_ROYALE_API_KEY")
    )


class _CRServer:
    """Persistent subprocess for CR API calls. Thread-safe via lock."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def _start(self):
        self._proc = subprocess.Popen(
            ["uv", "run", "--project", CR_PROJECT, "python", "-c", _SERVER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=CR_PROJECT,
        )

    def call(self, tool: str, args: dict) -> str:
        if not _token_available():
            return "Clash Royale API not available: no API token configured"
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            try:
                self._proc.stdin.write(json.dumps({"tool": tool, "args": args}) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                result = json.loads(line) if line else ""
                # Lists/dicts come back as JSON; stringify for Anthropic tool results
                if isinstance(result, (list, dict)):
                    return json.dumps(result, indent=2)
                return str(result)
            except Exception as e:
                print(f"[cr_server] call failed: {e}", flush=True)
                self._proc = None
                return f"CR API tool call failed: {e}"


_server = _CRServer()


def cr_available() -> bool:
    """Returns True if the CR API token is configured."""
    return _token_available()


def dispatch_cr_tool(name: str, tool_input: dict) -> str:
    """Dispatch a CR tool call."""
    return _server.call(name, tool_input)


# ── Anthropic tool definitions ──────────────────────────────────────────────

CR_TOOLS = [
    {
        "name": "get_player_recent_decks",
        "description": (
            "Fetch the decks a player has been using recently from their battle history. "
            "Returns deduplicated decks with win rates, usage counts, and card levels. "
            "Use this to understand the player's playstyle, preferred archetypes, and "
            "which decks are working for them on ladder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_tag": {
                    "type": "string",
                    "description": "Player tag (e.g. '#ABC123')",
                },
                "max_battles": {
                    "type": "integer",
                    "description": "Number of recent battles to scan (default 25)",
                    "default": 25,
                },
            },
            "required": ["player_tag"],
        },
    },
    {
        "name": "get_player_battlelog",
        "description": (
            "Fetch a summary of a player's recent battles: game mode, result, "
            "and both team and opponent deck lists. "
            "Useful for understanding which archetypes the player frequently faces on ladder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_tag": {
                    "type": "string",
                    "description": "Player tag (e.g. '#ABC123')",
                },
                "max_battles": {
                    "type": "integer",
                    "description": "Number of recent battles to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["player_tag"],
        },
    },
]
