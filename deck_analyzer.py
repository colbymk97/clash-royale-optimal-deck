import os
import anthropic

# ── System prompts ─────────────────────────────────────────────────────────

RECOMMEND_SYSTEM_PROMPT = """You are an expert Clash Royale coach and deck builder with deep knowledge of:
- Current meta decks, tier lists, and win conditions
- Card synergies, counters, and elixir efficiency
- Matchup strategies and general gameplay principles
- How card levels affect performance (underleveled cards lose stat checks)

When analyzing a player's card collection, you:
1. Use web search to check the **current** Clash Royale meta (patch notes, top ladder decks, recent tournament results)
2. Select only cards the player actually owns at the specified levels
3. Build decks that are realistic for the player's card levels — you account for level disadvantages
4. Provide actionable, specific strategy advice — not generic tips

Your deck suggestions MUST:
- Use exactly 8 cards per deck
- Only use cards from the player's provided collection
- Include a clear win condition
- Have reasonable average elixir (ideally 3.0–4.5)
- Vary in strategy (e.g., one beatdown, one cycle, one control/bridge spam)

Format your response as valid JSON matching this exact structure:
{
  "meta_context": "Brief 1-2 sentence summary of the current meta you found",
  "decks": [
    {
      "name": "Deck name (e.g., 'Hog Cycle' or 'Golem Beatdown')",
      "cards": ["Card1", "Card2", "Card3", "Card4", "Card5", "Card6", "Card7", "Card8"],
      "win_condition": "Primary win condition card(s)",
      "average_elixir": 3.1,
      "archetype": "Cycle | Beatdown | Control | Bridge Spam | Siege | Spell Bait",
      "difficulty": "Beginner | Intermediate | Advanced",
      "description": "2-3 sentence overview of why this deck works with the player's cards",
      "strategy": {
        "general": "Core gameplay loop and gameplan",
        "offense": "How to execute attacks and apply pressure",
        "defense": "How to defend and counter common threats",
        "key_synergies": ["Synergy 1 description", "Synergy 2 description"],
        "matchup_tips": ["Tip for common matchup 1", "Tip for common matchup 2", "Tip for common matchup 3"]
      },
      "level_notes": "Any notes about card levels affecting performance"
    }
  ]
}

Return ONLY the JSON object — no markdown code fences, no extra text."""


ANALYSIS_SYSTEM_PROMPT = """You are an expert Clash Royale coach performing a deep analysis of a player's deck.

Use web search to check the current meta, tier lists, and patch notes. Then evaluate the provided deck honestly.

Return ONLY a valid JSON object with this exact structure:
{
  "archetype": "Cycle | Beatdown | Control | Bridge Spam | Siege | Spell Bait | Other",
  "win_condition": "Primary win condition card(s)",
  "average_elixir": 3.5,
  "tier": "S | A | B | C | D",
  "tier_explanation": "1-2 sentences explaining the tier rating and why",
  "meta_viability": "1-2 sentences on how this deck fits the current meta",
  "strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "weaknesses": ["Weakness 1", "Weakness 2"],
  "suggested_swaps": [
    {
      "remove": "CardCurrentlyInDeck",
      "add": "ReplacementFromCollection",
      "reason": "Specific reason this swap improves the deck",
      "in_collection": true
    }
  ],
  "matchups": {
    "favorable": ["Archetype or deck type this deck beats"],
    "unfavorable": ["Archetype or deck type that beats this deck"],
    "neutral": ["Even matchups"]
  },
  "coaching": "3-4 paragraphs of specific coaching: how to pilot this deck, when to make pushes, defensive priorities, double elixir adjustments, and what separates good players from great players with this deck"
}

Only suggest swaps using cards explicitly listed in the player's collection.
Return ONLY the JSON — no markdown, no extra text."""


class DeckAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    # ── Recommendation Analysis ────────────────────────────────────────────

    def _build_recommend_message(self, cards: list[dict]) -> str:
        card_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in sorted(cards, key=lambda c: c.get("name", ""))
        )
        return f"""I have {len(cards)} cards unlocked in Clash Royale. Please search the web for the current meta and build me 3 optimal deck suggestions using only my cards below.

My card collection:
{card_lines}

Please:
1. Search the web for the current Clash Royale meta (top decks, tier lists, recent patch changes)
2. Analyze which of my cards fit best into competitive archetypes
3. Build 3 distinct deck suggestions (different archetypes) using ONLY my cards
4. Return JSON as specified in your instructions

Account for my card levels when making suggestions."""

    def analyze_stream(self, cards: list[dict]):
        """Stream 3 deck recommendations for a player's collection."""
        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=RECOMMEND_SYSTEM_PROMPT,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=[{"role": "user", "content": self._build_recommend_message(cards)}],
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    # ── Recommendation Chat ────────────────────────────────────────────────

    def _build_rec_chat_system(self, deck: dict, cards: list[dict]) -> str:
        card_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in sorted(cards, key=lambda c: c.get("name", ""))
        )
        strategy = deck.get("strategy", {})
        synergies = "\n".join(f"  • {s}" for s in strategy.get("key_synergies", []))
        return f"""You are an expert Clash Royale coach discussing a specific AI-recommended deck.

## The Deck
- **Name:** {deck.get("name", "Unknown")}
- **Archetype:** {deck.get("archetype", "Unknown")}
- **Cards:** {", ".join(deck.get("cards", []))}
- **Win Condition:** {deck.get("win_condition", "Unknown")}
- **Average Elixir:** {deck.get("average_elixir", "?")}

## Strategy
{strategy.get("general", "N/A")}
**Offense:** {strategy.get("offense", "N/A")}
**Defense:** {strategy.get("defense", "N/A")}
**Key Synergies:**
{synergies or "  N/A"}

## Player's Collection
{card_lines}

Answer questions specifically about this deck. Be practical and use Clash Royale terminology."""

    def chat_stream(self, deck: dict, cards: list[dict], history: list[dict], user_message: str):
        """Stream a strategy chat response for a recommended deck."""
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})
        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=self._build_rec_chat_system(deck, cards),
            messages=messages,
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    # ── Saved Deck Analysis ────────────────────────────────────────────────

    def _build_analysis_message(self, deck_cards: list[dict], collection: list[dict]) -> str:
        deck_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in deck_cards
        )
        collection_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in sorted(collection, key=lambda c: c.get("name", ""))
        )
        return f"""Please analyze this Clash Royale deck. Search the web for the current meta first.

## The Deck (8 cards)
{deck_lines}

## Player's Full Card Collection (for swap suggestions)
{collection_lines}

Search the current meta, evaluate this deck, and return JSON as specified. Only suggest swaps using cards from the collection above."""

    def analyze_saved_deck_stream(self, deck_cards: list[dict], collection: list[dict]):
        """Stream a one-time deep analysis of a saved/uploaded deck."""
        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=6000,
            thinking={"type": "adaptive"},
            system=ANALYSIS_SYSTEM_PROMPT,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=[{"role": "user", "content": self._build_analysis_message(deck_cards, collection)}],
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    # ── Saved Deck Fine-Tune Chat ──────────────────────────────────────────

    def _build_saved_deck_chat_system(
        self, deck_cards: list[dict], analysis: dict | None, collection: list[dict]
    ) -> str:
        card_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in deck_cards
        )
        collection_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in sorted(collection, key=lambda c: c.get("name", ""))
        )

        analysis_section = ""
        if analysis:
            a = analysis
            swaps = "\n".join(
                f"  • Replace {s['remove']} → {s['add']}: {s['reason']}"
                for s in a.get("suggested_swaps", [])
            )
            analysis_section = f"""
## Prior Deep Analysis
- **Archetype:** {a.get("archetype", "?")}
- **Tier:** {a.get("tier", "?")} — {a.get("tier_explanation", "")}
- **Meta Viability:** {a.get("meta_viability", "")}
- **Strengths:** {", ".join(a.get("strengths", []))}
- **Weaknesses:** {", ".join(a.get("weaknesses", []))}
- **Suggested Swaps:**
{swaps or "  None identified"}
"""

        return f"""You are an expert Clash Royale coach helping a player fine-tune and master their deck.

## The Deck
{card_lines}
{analysis_section}
## Player's Full Card Collection
{collection_lines}

Your role:
- Help the player improve this specific deck through targeted card swaps (only from their collection)
- Explain why specific swaps make the deck stronger or better suited to their playstyle
- Discuss matchups, positioning, timing, elixir management, and win conditions
- Reference the prior analysis when relevant — build on it rather than repeating it
- Be direct, specific, and practical. Use Clash Royale terminology naturally.
- When suggesting swaps, always confirm the card is in their collection above."""

    def saved_deck_chat_stream(
        self,
        deck_cards: list[dict],
        analysis: dict | None,
        collection: list[dict],
        history: list[dict],
        user_message: str,
    ):
        """Stream a fine-tune coaching chat response for a saved deck."""
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})
        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=self._build_saved_deck_chat_system(deck_cards, analysis, collection),
            messages=messages,
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text
