from __future__ import annotations
import os
import anthropic
from wiki_context import WIKI_TOOLS, dispatch_tool as _dispatch_wiki_tool
from cr_context import CR_TOOLS, cr_available, dispatch_cr_tool
from prompts import (
    _build_recommend_system,
    ANALYSIS_SYSTEM_PROMPT,
    BATTLE_ANALYSIS_SYSTEM_PROMPT,
    recommend_user_msg,
    analysis_user_msg,
    battle_analysis_user_msg,
    rec_chat_system,
    saved_deck_chat_system,
)

_CR_TOOL_NAMES = {t["name"] for t in CR_TOOLS}


def _all_tools() -> list:
    """Return wiki tools plus CR API tools when a token is configured."""
    return WIKI_TOOLS + (CR_TOOLS if cr_available() else [])


_MAX_TOOL_RESULT = 2_000  # chars; keeps context lean across agentic rounds


def dispatch_tool(name: str, tool_input: dict) -> str:
    """Route a tool call to the wiki server or the CR API server."""
    if name in _CR_TOOL_NAMES:
        result = dispatch_cr_tool(name, tool_input)
    else:
        result = _dispatch_wiki_tool(name, tool_input)
    if isinstance(result, str) and len(result) > _MAX_TOOL_RESULT:
        result = result[:_MAX_TOOL_RESULT] + "\n…[truncated]"
    return result


# ── Tool status helper ──────────────────────────────────────────────────────

def _tool_status(tool_blocks) -> str:
    labels = []
    for b in tool_blocks:
        inp = b.input or {}
        if b.name == "get_card_info":
            labels.append(f"card info: {inp.get('card_name', '...')}")
        elif b.name == "get_card_counters":
            labels.append(f"counters: {inp.get('card_name', '...')}")
        elif b.name == "get_card_synergies":
            labels.append(f"synergies: {inp.get('card_name', '...')}")
        elif b.name == "search_deck_strategies":
            labels.append("deck strategies")
        elif b.name == "get_game_mechanics":
            labels.append(f"mechanics: {inp.get('topic', '...')}")
        elif b.name == "search_wiki":
            q = inp.get("query", "...")
            labels.append(f"wiki: {q[:30]}" if len(q) > 30 else f"wiki: {q}")
        elif b.name == "get_player_recent_decks":
            labels.append(f"live decks: {inp.get('player_tag', '...')}")
        elif b.name == "get_player_battlelog":
            labels.append(f"battle log: {inp.get('player_tag', '...')}")
        else:
            labels.append(b.name.replace("_", " "))
    return "Consulting wiki — " + ", ".join(labels)


# ── DeckAnalyzer ────────────────────────────────────────────────────────────

class DeckAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # ── Shared helpers ──────────────────────────────────────────────────────

    def _log_usage_msg(self, label: str, msg):
        try:
            usage = msg.usage
            inp, out = usage.input_tokens, usage.output_tokens
            cost = (inp * 3 + out * 15) / 1_000_000
            print(f"[tokens] {label} — input: {inp:,}  output: {out:,}  est cost: ${cost:.4f}", flush=True)
        except Exception as e:
            print(f"[tokens] {label} — could not read usage: {e}", flush=True)

    def _log_usage(self, label: str, stream):
        try:
            self._log_usage_msg(label, stream.get_final_message())
        except Exception as e:
            print(f"[tokens] {label} — could not read usage: {e}", flush=True)

    def _stream_text(self, stream):
        for event in stream:
            if (
                event.type == "content_block_delta"
                and hasattr(event.delta, "type")
                and event.delta.type == "text_delta"
            ):
                yield event.delta.text

    # ── Agentic loops ───────────────────────────────────────────────────────

    def _buffered_agent(self, system: str, messages: list, max_tokens: int, label: str, max_rounds: int = 10):
        """
        Non-streaming agentic loop for JSON output (analyze functions).
        Yields ("status", str) during tool rounds, ("text", str) for the final response,
        and ("usage", dict) once at the end with cumulative token counts.
        """
        usage_totals = {"input_tokens": 0, "output_tokens": 0}

        def _accum(r):
            try:
                usage_totals["input_tokens"] += r.usage.input_tokens
                usage_totals["output_tokens"] += r.usage.output_tokens
            except Exception:
                pass

        def _emit_text_and_usage(r):
            for block in r.content:
                if hasattr(block, "text") and block.text:
                    yield ("text", block.text)
            cost = (usage_totals["input_tokens"] * 3 + usage_totals["output_tokens"] * 15) / 1_000_000
            yield ("usage", {**usage_totals, "cost": round(cost, 6)})
            self._log_usage_msg(label, r)

        for _ in range(max_rounds):
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system,
                tools=_all_tools(),
                messages=messages,
            )
            _accum(resp)

            if resp.stop_reason == "tool_use":
                tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                yield ("status", _tool_status(tool_blocks))

                results = []
                for b in tool_blocks:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": dispatch_tool(b.name, b.input),
                    })
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": results})
            else:
                yield from _emit_text_and_usage(resp)
                return

        # All rounds used tool_use — force one final text-only call so we always
        # produce a response rather than silently returning nothing.
        yield ("status", "Generating response…")
        final = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        _accum(final)
        yield from _emit_text_and_usage(final)

    def _streaming_agent(self, system: str, messages: list, max_tokens: int, label: str):
        """
        Streaming chat agent.
        - No tools: text yielded as a fast burst (buffered first call).
        - Tools used: status events (before any text), then true word-by-word streaming for the
          final response. Status events always precede text, so JS typing-indicator logic is simple.
        Yields ("status", str), ("text", str), and ("usage", dict) tuples.
        """
        usage_totals = {"input_tokens": 0, "output_tokens": 0}

        # First call: buffer so we commit nothing to the client until we know the outcome
        buffered: list[str] = []
        with self.client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            tools=_all_tools(),
            messages=messages,
        ) as stream:
            for chunk in self._stream_text(stream):
                buffered.append(chunk)
            final_msg = stream.get_final_message()
            try:
                usage_totals["input_tokens"] += final_msg.usage.input_tokens
                usage_totals["output_tokens"] += final_msg.usage.output_tokens
            except Exception:
                pass
            self._log_usage_msg(label, final_msg)

        if final_msg.stop_reason == "end_turn":
            for chunk in buffered:
                yield ("text", chunk)
            cost = (usage_totals["input_tokens"] * 3 + usage_totals["output_tokens"] * 15) / 1_000_000
            yield ("usage", {**usage_totals, "cost": round(cost, 6)})
            return

        # Tool use triggered — discard pre-tool buffered text, handle rounds
        tool_blocks = [b for b in final_msg.content if b.type == "tool_use"]
        yield ("status", _tool_status(tool_blocks))
        results = []
        for b in tool_blocks:
            results.append({
                "type": "tool_result",
                "tool_use_id": b.id,
                "content": dispatch_tool(b.name, b.input),
            })
        messages.append({"role": "assistant", "content": final_msg.content})
        messages.append({"role": "user", "content": results})

        # Remaining non-streaming tool rounds, then a fresh streaming final response
        for _ in range(8):
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system,
                tools=_all_tools(),
                messages=messages,
            )
            try:
                usage_totals["input_tokens"] += resp.usage.input_tokens
                usage_totals["output_tokens"] += resp.usage.output_tokens
            except Exception:
                pass
            if resp.stop_reason == "tool_use":
                tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                yield ("status", _tool_status(tool_blocks))
                results = []
                for b in tool_blocks:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": dispatch_tool(b.name, b.input),
                    })
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": results})
            else:
                yield ("status", "Generating response…")
                with self.client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                ) as stream:
                    for chunk in self._stream_text(stream):
                        yield ("text", chunk)
                    final_msg2 = stream.get_final_message()
                    try:
                        usage_totals["input_tokens"] += final_msg2.usage.input_tokens
                        usage_totals["output_tokens"] += final_msg2.usage.output_tokens
                    except Exception:
                        pass
                    self._log_usage_msg(label + "-final", final_msg2)
                cost = (usage_totals["input_tokens"] * 3 + usage_totals["output_tokens"] * 15) / 1_000_000
                yield ("usage", {**usage_totals, "cost": round(cost, 6)})
                return

    # ── Public API ──────────────────────────────────────────────────────────

    def analyze_stream(
        self,
        cards: list[dict],
        player_tag: str | None = None,
        num_decks: int = 3,
        strategies: list[str] | None = None,
        selected_cards: list[str] | None = None,
        previous_decks: list[list[str]] | None = None,
    ):
        """Deck recommendations via agentic loop. Yields (kind, value) tuples."""
        system = _build_recommend_system(num_decks=num_decks, strategies=strategies)
        user_msg = recommend_user_msg(
            cards, player_tag,
            num_decks=num_decks,
            strategies=strategies,
            selected_cards=selected_cards,
            previous_decks=previous_decks,
        )
        messages = [{"role": "user", "content": user_msg}]
        max_tokens = min(8192, 4000 + num_decks * 1000)  # scales with deck count, capped at model max
        yield from self._buffered_agent(system, messages, max_tokens, "recommend", max_rounds=6)

    def analyze_battle_stream(self, battle: dict):
        """Battle matchup analysis via agentic loop. Yields (kind, value) tuples."""
        messages = [{"role": "user", "content": battle_analysis_user_msg(battle)}]
        yield from self._buffered_agent(BATTLE_ANALYSIS_SYSTEM_PROMPT, messages, 2500, "battle-analysis")

    def chat_stream(self, deck: dict, cards: list[dict], history: list[dict], user_message: str, player_tag: str | None = None):
        """Recommendation deck chat via agentic loop. Yields (kind, value) tuples."""
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})
        yield from self._streaming_agent(rec_chat_system(deck, cards, player_tag), messages, 1024, "rec-chat")

    def analyze_saved_deck_stream(self, deck_cards: list[dict], collection: list[dict], player_tag: str | None = None):
        """Deep analysis of a saved deck via agentic loop. Yields (kind, value) tuples."""
        messages = [{"role": "user", "content": analysis_user_msg(deck_cards, collection, player_tag)}]
        yield from self._buffered_agent(ANALYSIS_SYSTEM_PROMPT, messages, 3000, "saved-deck-analysis")

    def saved_deck_chat_stream(
        self,
        deck_cards: list[dict],
        analysis: dict | None,
        collection: list[dict],
        history: list[dict],
        user_message: str,
        player_tag: str | None = None,
    ):
        """Saved deck fine-tune chat via agentic loop. Yields (kind, value) tuples."""
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})
        yield from self._streaming_agent(
            saved_deck_chat_system(deck_cards, analysis, collection, player_tag),
            messages,
            1024,
            "saved-deck-chat",
        )
