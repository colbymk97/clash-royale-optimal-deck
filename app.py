import os
import json
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from dotenv import load_dotenv
from deck_analyzer import DeckAnalyzer
from clash_api import ClashRoyaleAPI
import db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

deck_analyzer = DeckAnalyzer()
clash_api = ClashRoyaleAPI()

db.init_db()


# ── Pages ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Clash Royale API proxies ───────────────────────────────────────────────

@app.route("/api/fetch-cards/<player_tag>")
def fetch_player_cards(player_tag):
    if not clash_api.api_key:
        return jsonify({"error": "Clash Royale API key not configured. Please add cards manually."}), 503

    tag = player_tag.strip()
    if not tag.startswith("#"):
        tag = "#" + tag

    result = clash_api.get_player_cards(tag)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/all-cards")
def get_all_cards():
    if not clash_api.api_key:
        return jsonify({"cards": _fallback_card_list()})

    result = clash_api.get_all_cards()
    if "error" in result:
        return jsonify({"cards": _fallback_card_list()})
    return jsonify(result)


# ── Deck analysis (streaming) ──────────────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def analyze_deck():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    cards = data.get("cards", [])
    if not cards:
        return jsonify({"error": "No cards provided"}), 400
    if len(cards) < 8:
        return jsonify({"error": "You need at least 8 cards to build a deck"}), 400

    def generate():
        accumulated = ""
        try:
            for chunk in deck_analyzer.analyze_stream(cards):
                accumulated += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Parse and persist the completed response
            save_info = {}
            try:
                json_start = accumulated.find("{")
                json_end = accumulated.rfind("}")
                if json_start != -1 and json_end != -1:
                    parsed = json.loads(accumulated[json_start:json_end + 1])
                    save_info = db.save_session(
                        cards=cards,
                        meta_context=parsed.get("meta_context", ""),
                        decks=parsed.get("decks", []),
                    )
            except (json.JSONDecodeError, Exception):
                pass  # Don't fail the stream if saving fails

            yield f"data: {json.dumps({'done': True, **save_info})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Session history ────────────────────────────────────────────────────────

@app.route("/api/sessions")
def list_sessions():
    sessions = db.list_sessions()
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/<int:session_id>")
def get_session(session_id):
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)


# ── Deck chat (streaming) ──────────────────────────────────────────────────

@app.route("/api/decks/<int:deck_id>/chat", methods=["GET"])
def get_chat(deck_id):
    if not db.get_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    messages = db.get_chat_history(deck_id)
    return jsonify({"messages": messages})


@app.route("/api/decks/<int:deck_id>/chat", methods=["POST"])
def post_chat(deck_id):
    data = request.get_json()
    user_message = (data or {}).get("message", "").strip()
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    deck_data = db.get_deck(deck_id)
    if not deck_data:
        return jsonify({"error": "Deck not found"}), 404

    history = db.get_chat_history(deck_id)
    db.save_chat_message(deck_id, "user", user_message)

    def generate():
        full_response = ""
        try:
            for chunk in deck_analyzer.chat_stream(
                deck_data["deck"],
                deck_data["cards"],
                history,
                user_message,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            db.save_chat_message(deck_id, "assistant", full_response)
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _fallback_card_list():
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
        "Super Witch", "Firecracker",
    ]


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5000)
