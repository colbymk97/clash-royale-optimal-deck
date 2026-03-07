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

    def _build_user_message(self, cards: list[dict]) -> str:
        """Format the user's card collection into a prompt."""
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
                # Only yield text deltas from the final response (not tool use)
                if (
                    event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text
