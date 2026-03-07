import os
import requests

CLASH_API_BASE = "https://api.clashroyale.com/v1"


class ClashRoyaleAPI:
    def __init__(self):
        self.api_key = os.environ.get("CLASH_ROYALE_API_KEY", "")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            })

    def _get(self, endpoint: str, params: dict = None) -> dict:
        try:
            url = f"{CLASH_API_BASE}{endpoint}"
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return {"error": "Player not found. Check the player tag and try again."}
            elif resp.status_code == 403:
                return {"error": "API key doesn't have access to this resource."}
            elif resp.status_code == 503:
                return {"error": "Clash Royale API is temporarily unavailable. Try again later."}
            else:
                return {"error": f"API request failed with status {resp.status_code}"}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your connection and try again."}
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}

    def get_player_cards(self, player_tag: str) -> dict:
        """Fetch a player's unlocked cards with levels."""
        # URL-encode the # in the tag
        encoded_tag = player_tag.replace("#", "%23")
        result = self._get(f"/players/{encoded_tag}")

        if "error" in result:
            return result

        # Extract the cards array from the player profile
        raw_cards = result.get("cards", [])
        if not raw_cards:
            return {"error": "No cards found for this player. The account may be new."}

        cards = []
        for card in raw_cards:
            cards.append({
                "name": card.get("name", "Unknown"),
                "level": card.get("level", 1),
                "maxLevel": card.get("maxLevel", 14),
                "id": card.get("id"),
                "iconUrl": card.get("iconUrls", {}).get("medium", ""),
                "elixirCost": card.get("elixirCost"),
                "rarity": card.get("rarity", ""),
            })

        player_name = result.get("name", "Unknown Player")
        trophies = result.get("trophies", 0)
        arena = result.get("arena", {}).get("name", "")

        return {
            "player": {
                "name": player_name,
                "tag": player_tag,
                "trophies": trophies,
                "arena": arena,
            },
            "cards": cards,
            "total": len(cards),
        }

    def get_all_cards(self) -> dict:
        """Fetch the full list of cards from the API."""
        result = self._get("/cards")

        if "error" in result:
            return result

        raw_cards = result.get("items", [])
        cards = []
        for card in raw_cards:
            cards.append({
                "name": card.get("name", "Unknown"),
                "id": card.get("id"),
                "maxLevel": card.get("maxLevel", 14),
                "iconUrl": card.get("iconUrls", {}).get("medium", ""),
                "elixirCost": card.get("elixirCost"),
                "rarity": card.get("rarity", ""),
            })

        return {"cards": sorted(cards, key=lambda c: c["name"])}
