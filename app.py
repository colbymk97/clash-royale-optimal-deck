import os
import json
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from dotenv import load_dotenv
from deck_analyzer import DeckAnalyzer
from clash_api import ClashRoyaleAPI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

deck_analyzer = DeckAnalyzer()
clash_api = ClashRoyaleAPI()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch-cards/<player_tag>")
def fetch_player_cards(player_tag):
    """Fetch a player's unlocked cards and levels from the Clash Royale API."""
    if not clash_api.api_key:
        return jsonify({"error": "Clash Royale API key not configured. Please add cards manually."}), 503

    # Normalize tag: ensure it starts with #
    tag = player_tag.strip()
    if not tag.startswith("#"):
        tag = "#" + tag

    result = clash_api.get_player_cards(tag)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/api/all-cards")
def get_all_cards():
    """Return a list of all known Clash Royale cards for the manual card picker."""
    if not clash_api.api_key:
        # Return a static fallback list of common cards
        return jsonify({"cards": get_fallback_card_list()})

    result = clash_api.get_all_cards()
    if "error" in result:
        return jsonify({"cards": get_fallback_card_list()})

    return jsonify(result)


@app.route("/api/analyze", methods=["POST"])
def analyze_deck():
    """Analyze user's cards and stream 3 optimal deck suggestions."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    cards = data.get("cards", [])
    if not cards:
        return jsonify({"error": "No cards provided"}), 400

    if len(cards) < 8:
        return jsonify({"error": "You need at least 8 cards to build a deck"}), 400

    def generate():
        try:
            for chunk in deck_analyzer.analyze_stream(cards):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def get_fallback_card_list():
    """Static list of Clash Royale cards when the API is unavailable."""
    return [
        "Archer Queen", "Archers", "Baby Dragon", "Balloon", "Bandit",
        "Barbarian Barrel", "Barbarians", "Bats", "Battle Healer", "Battle Ram",
        "Bomb Tower", "Bowler", "Cannon", "Cannon Cart", "Clone",
        "Dark Prince", "Dart Goblin", "Earthquake", "Electro Dragon",
        "Electro Giant", "Electro Spirit", "Electro Wizard", "Elite Barbarians",
        "Executioner", "Fire Spirit", "Fireball", "Fisherman", "Flying Machine",
        "Freeze", "Giant", "Giant Skeleton", "Goblin Barrel", "Goblin Cage",
        "Goblin Gang", "Goblin Giant", "Goblin Machine", "Goblins",
        "Golden Knight", "Golem", "Grand Warden", "Guards", "Hunter",
        "Ice Golem", "Ice Spirit", "Ice Wizard", "Inferno Dragon",
        "Inferno Tower", "Knight", "Lava Hound", "Lumberjack",
        "Magic Archer", "Mega Knight", "Mega Minion", "Mighty Miner",
        "Mini P.E.K.K.A", "Minion Horde", "Minions", "Monk",
        "Mortar", "Musketeer", "Night Witch", "P.E.K.K.A", "Phoenix",
        "Poison", "Prince", "Princess", "Ram Rider", "Rage",
        "Rocket", "Royal Delivery", "Royal Ghost", "Royal Giant",
        "Royal Hogs", "Royal Recruits", "Skeleton Army", "Skeleton Barrel",
        "Skeleton Dragons", "Skeleton King", "Skeletons", "Sparky",
        "Spear Goblins", "Tesla", "The Log", "Three Musketeers",
        "Tombstone", "Tornado", "Valkyrie", "Wall Breakers",
        "Witch", "Wizard", "X-Bow", "Zap", "Zappies",
        "Goblin Drill", "Little Prince", "Hog Rider", "Electro Bat",
        "Super Witch", "Firecracker"
    ]


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5000)
