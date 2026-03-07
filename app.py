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


# ── Recommendation Analysis (streaming) ───────────────────────────────────

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

            save_info = {}
            try:
                j0, j1 = accumulated.find("{"), accumulated.rfind("}")
                if j0 != -1 and j1 != -1:
                    parsed = json.loads(accumulated[j0:j1 + 1])
                    save_info = db.save_session(
                        cards=cards,
                        meta_context=parsed.get("meta_context", ""),
                        decks=parsed.get("decks", []),
                    )
            except Exception:
                pass

            yield f"data: {json.dumps({'done': True, **save_info})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Recommendation Sessions ────────────────────────────────────────────────

@app.route("/api/sessions")
def list_sessions():
    return jsonify({"sessions": db.list_sessions()})


@app.route("/api/sessions/<int:session_id>")
def get_session(session_id):
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)


# ── Recommendation Deck Chat (streaming) ──────────────────────────────────

@app.route("/api/decks/<int:deck_id>/chat", methods=["GET"])
def get_chat(deck_id):
    if not db.get_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"messages": db.get_chat_history(deck_id)})


@app.route("/api/decks/<int:deck_id>/chat", methods=["POST"])
def post_chat(deck_id):
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
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
                deck_data["deck"], deck_data["cards"], history, user_message
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


# ── Saved Decks CRUD ───────────────────────────────────────────────────────

@app.route("/api/saved-decks", methods=["GET"])
def list_saved_decks():
    return jsonify({"decks": db.list_saved_decks()})


@app.route("/api/saved-decks", methods=["POST"])
def create_saved_deck():
    data = request.get_json() or {}
    name = data.get("name", "My Deck").strip() or "My Deck"
    cards = data.get("cards", [])
    source = data.get("source", "manual")

    if len(cards) != 8:
        return jsonify({"error": "Deck must have exactly 8 cards"}), 400
    names = [c["name"] for c in cards]
    if len(names) != len(set(n.lower() for n in names)):
        return jsonify({"error": "Deck cannot contain duplicate cards"}), 400

    deck_id = db.create_saved_deck(name=name, cards=cards, source=source)
    return jsonify({"id": deck_id}), 201


@app.route("/api/saved-decks/<int:deck_id>", methods=["GET"])
def get_saved_deck(deck_id):
    deck = db.get_saved_deck(deck_id)
    if not deck:
        return jsonify({"error": "Deck not found"}), 404
    return jsonify(deck)


@app.route("/api/saved-decks/<int:deck_id>", methods=["PUT"])
def update_saved_deck(deck_id):
    data = request.get_json() or {}
    name = data.get("name")
    cards = data.get("cards")

    if cards is not None:
        if len(cards) != 8:
            return jsonify({"error": "Deck must have exactly 8 cards"}), 400
        names = [c["name"] for c in cards]
        if len(names) != len(set(n.lower() for n in names)):
            return jsonify({"error": "Deck cannot contain duplicate cards"}), 400
        # Clear analysis and chat when cards change so a fresh analysis can be run
        db.clear_saved_deck_analysis(deck_id)

    if not db.update_saved_deck(deck_id, name=name, cards=cards):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/saved-decks/<int:deck_id>", methods=["DELETE"])
def delete_saved_deck(deck_id):
    if not db.delete_saved_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"ok": True})


# ── Saved Deck Analysis (streaming, run once) ─────────────────────────────

@app.route("/api/saved-decks/<int:deck_id>/analysis", methods=["GET"])
def get_saved_deck_analysis(deck_id):
    if not db.get_saved_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify(db.get_saved_deck_analysis(deck_id) or {})


@app.route("/api/saved-decks/<int:deck_id>/analysis", methods=["POST"])
def run_saved_deck_analysis(deck_id):
    deck = db.get_saved_deck(deck_id)
    if not deck:
        return jsonify({"error": "Deck not found"}), 404

    data = request.get_json() or {}
    collection = data.get("collection", [])

    def generate():
        accumulated = ""
        try:
            for chunk in deck_analyzer.analyze_saved_deck_stream(deck["cards"], collection):
                accumulated += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            try:
                j0, j1 = accumulated.find("{"), accumulated.rfind("}")
                if j0 != -1 and j1 != -1:
                    parsed = json.loads(accumulated[j0:j1 + 1])
                    db.save_saved_deck_analysis(deck_id, parsed, collection)
                    yield f"data: {json.dumps({'done': True, 'analysis': parsed})}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception:
                yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Saved Deck Fine-Tune Chat (streaming) ─────────────────────────────────

@app.route("/api/saved-decks/<int:deck_id>/chat", methods=["GET"])
def get_saved_deck_chat(deck_id):
    if not db.get_saved_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"messages": db.get_saved_deck_chat(deck_id)})


@app.route("/api/saved-decks/<int:deck_id>/chat", methods=["POST"])
def post_saved_deck_chat(deck_id):
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    collection = data.get("collection", [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    deck = db.get_saved_deck(deck_id)
    if not deck:
        return jsonify({"error": "Deck not found"}), 404

    analysis_row = db.get_saved_deck_analysis(deck_id)
    analysis = analysis_row["analysis"] if analysis_row else None
    history = db.get_saved_deck_chat(deck_id)
    db.append_saved_deck_chat(deck_id, "user", user_message)

    def generate():
        full_response = ""
        try:
            for chunk in deck_analyzer.saved_deck_chat_stream(
                deck["cards"], analysis, collection, history, user_message
            ):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            db.append_saved_deck_chat(deck_id, "assistant", full_response)
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
