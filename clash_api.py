import os
import json
import logging
import requests

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "clash_api.log"),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

CLASH_API_BASE = "https://proxy.royaleapi.dev/v1"


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

        logging.debug("Raw player cards response:\n%s", json.dumps(raw_cards, indent=2))

        rarity_offset = {
            "common": 0,
            "rare": 2,
            "epic": 5,
            "legendary": 8,
            "champion": 10,
        }

        cards = []
        for card in raw_cards:
            rarity = card.get("rarity", "").lower()
            offset = rarity_offset.get(rarity, 0)
            display_level = card.get("level", 1) + offset
            cards.append({
                "name": card.get("name", "Unknown"),
                "level": display_level,
                "maxLevel": 16,
                "id": card.get("id"),
                "iconUrl": card.get("iconUrls", {}).get("medium", ""),
                "elixirCost": card.get("elixirCost"),
                "rarity": card.get("rarity", ""),
            })

        # Extract current battle deck (same level normalization)
        current_deck = []
        for card in result.get("currentDeck", []):
            rarity = card.get("rarity", "").lower()
            offset = rarity_offset.get(rarity, 0)
            current_deck.append({
                "name": card.get("name", "Unknown"),
                "level": card.get("level", 1) + offset,
                "maxLevel": 16,
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
            "current_deck": current_deck,
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

    def get_player_battlelog(self, player_tag: str) -> dict:
        """Fetch a player's recent battle log."""
        encoded_tag = player_tag.replace("#", "%23")
        result = self._get(f"/players/{encoded_tag}/battlelog")

        if "error" in result:
            return result

        battles_raw = result if isinstance(result, list) else result.get("items", [])

        rarity_offset = {
            "common": 0, "rare": 2, "epic": 5, "legendary": 8, "champion": 10,
        }

        battles = []
        for b in battles_raw:
            team = (b.get("team") or [{}])[0]
            opp = (b.get("opponent") or [{}])[0]
            team_crowns = team.get("crowns", 0)
            opp_crowns = opp.get("crowns", 0)

            def norm_cards(card_list):
                out = []
                for c in card_list:
                    rarity = c.get("rarity", "").lower()
                    offset = rarity_offset.get(rarity, 0)
                    out.append({
                        "name": c.get("name", "Unknown"),
                        "level": c.get("level", 1) + offset,
                        "elixirCost": c.get("elixirCost"),
                        "rarity": c.get("rarity", ""),
                    })
                return out

            battles.append({
                "battleTime": b.get("battleTime", ""),
                "gameMode": b.get("gameMode", {}).get("name", ""),
                "arena": b.get("arena", {}).get("name", ""),
                "result": "win" if team_crowns > opp_crowns else ("draw" if team_crowns == opp_crowns else "loss"),
                "team_crowns": team_crowns,
                "opponent_crowns": opp_crowns,
                "team_name": team.get("name", ""),
                "team_tag": team.get("tag", ""),
                "team_trophies": team.get("startingTrophies", team.get("trophies", 0)),
                "team_cards": norm_cards(team.get("cards", [])),
                "opponent_name": opp.get("name", ""),
                "opponent_tag": opp.get("tag", ""),
                "opponent_trophies": opp.get("startingTrophies", opp.get("trophies", 0)),
                "opponent_cards": norm_cards(opp.get("cards", [])),
            })

        return {"battles": battles}
