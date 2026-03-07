import os
import anthropic

SYSTEM_PROMPT = """You are an expert Clash Royale coach and deck builder with deep knowledge of:
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
      "level_notes": "Any notes about card levels affecting performance (e.g., if some cards are underleveled)"
    }
  ]
}

Return ONLY the JSON object — no markdown code fences, no extra text."""


class DeckAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    # ── Deck Analysis ──────────────────────────────────────────────────────

    def _build_user_message(self, cards: list[dict]) -> str:
        card_lines = []
        for card in sorted(cards, key=lambda c: c.get("name", "")):
            name = card.get("name", "Unknown")
            level = card.get("level", "?")
            max_level = card.get("maxLevel", 14)
            card_lines.append(f"  - {name} (Level {level}/{max_level})")

        cards_text = "\n".join(card_lines)
        total = len(cards)

        return f"""I have {total} cards unlocked in Clash Royale. Please search the web for the current Clash Royale meta and build me 3 optimal deck suggestions using only the cards I have listed below.

My card collection:
{cards_text}

Please:
1. First search the web for the current Clash Royale meta (top decks, tier lists, recent patch changes)
2. Analyze which of my cards fit best into competitive archetypes
3. Build 3 distinct deck suggestions (different archetypes/strategies) using ONLY my cards
4. Return your suggestions as the JSON structure specified in your instructions

Remember to account for my card levels when making suggestions."""

    def analyze_stream(self, cards: list[dict]):
        """Stream the deck analysis response from Claude using web search."""
        user_message = self._build_user_message(cards)

        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    # ── Deck Chat ──────────────────────────────────────────────────────────

    def _build_chat_system(self, deck: dict, cards: list[dict]) -> str:
        card_lines = "\n".join(
            f"  - {c['name']} (Level {c['level']}/{c.get('maxLevel', 14)})"
            for c in sorted(cards, key=lambda c: c.get("name", ""))
        )
        strategy = deck.get("strategy", {})
        synergies = "\n".join(f"  • {s}" for s in strategy.get("key_synergies", []))

        return f"""You are an expert Clash Royale coach having a deep-dive conversation about a specific deck.

## The Deck Being Discussed
- **Name:** {deck.get("name", "Unknown")}
- **Archetype:** {deck.get("archetype", "Unknown")}
- **Cards:** {", ".join(deck.get("cards", []))}
- **Win Condition:** {deck.get("win_condition", "Unknown")}
- **Average Elixir:** {deck.get("average_elixir", "?")}
- **Difficulty:** {deck.get("difficulty", "?")}

## Deck Strategy Overview
{strategy.get("general", "N/A")}

**Offense:** {strategy.get("offense", "N/A")}
**Defense:** {strategy.get("defense", "N/A")}

**Key Synergies:**
{synergies or "  N/A"}

## Player's Full Card Collection
{card_lines}

---
Answer questions thoroughly and specifically about this deck. Cover topics like:
- Exact card placements and timing
- Elixir management and when to make pushes
- How to handle specific threats and matchups
- Double elixir and overtime adjustments
- Common mistakes to avoid
- How the player's card levels affect the strategy

Be conversational, specific, and use Clash Royale terminology naturally. Keep responses focused and practical."""

    def chat_stream(self, deck: dict, cards: list[dict], history: list[dict], user_message: str):
        """Stream a chat response about a specific deck."""
        system = self._build_chat_system(deck, cards)

        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]
        messages.append({"role": "user", "content": user_message})

        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text
