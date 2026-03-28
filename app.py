import os
import json
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from dotenv import load_dotenv
from deck_analyzer import DeckAnalyzer
from clash_api import ClashRoyaleAPI
from cr_context import cr_available
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


@app.route("/battle-log")
def battle_log():
    return render_template("battle_log.html")


@app.route("/api/cr-status")
def cr_status():
    available = cr_available()
    message = (
        "Clash Royale live data tools are active. The AI can query your battle history and recent decks."
        if available
        else "Clash Royale live data tools are not available: set CLASH_ROYALE_API_KEY (or CLASH_ROYALE_API_TOKEN) in your .env file."
    )
    return jsonify({"available": available, "message": message})


# ── Clash Royale API proxies ───────────────────────────────────────────────

@app.route("/api/all-cards")
def get_all_cards():
    if not clash_api.api_key:
        return jsonify({"cards": []})
    result = clash_api.get_all_cards()
    if "error" in result:
        return jsonify({"cards": []})
    return jsonify(result)


# ── Profiles ───────────────────────────────────────────────────────────────

@app.route("/api/profiles", methods=["GET"])
def list_profiles():
    return jsonify({"profiles": db.list_profiles()})


@app.route("/api/profiles", methods=["POST"])
def create_profile():
    """Create a profile by player tag — fetches from CR API automatically."""
    data = request.get_json() or {}
    tag = data.get("player_tag", "").strip()
    if not tag:
        return jsonify({"error": "player_tag is required"}), 400
    if not tag.startswith("#"):
        tag = "#" + tag

    if not clash_api.api_key:
        return jsonify({"error": "Clash Royale API key not configured on this server."}), 503

    # Check for duplicate
    existing = db.get_profile_by_tag(tag)
    if existing:
        return jsonify({"error": f"A profile for {tag} already exists."}), 409

    result = clash_api.get_player_cards(tag)
    if "error" in result:
        return jsonify(result), 400

    player = result["player"]
    cards = _dedup_cards(result["cards"])
    profile_id = db.create_profile(
        player_tag=player["tag"],
        player_name=player["name"],
        trophies=player["trophies"],
        arena=player["arena"],
        collection=cards,
    )

    # Auto-import current battle deck if present
    current_deck = result.get("current_deck", [])
    if len(current_deck) == 8:
        deck_name = f"{player['name']}'s Deck"
        db.create_saved_deck(name=deck_name, cards=current_deck, source="api", profile_id=profile_id)

    # Auto-import battle log
    try:
        blog = clash_api.get_player_battlelog(player["tag"])
        if "battles" in blog:
            db.save_battles(profile_id, blog["battles"])
    except Exception:
        pass

    profile = db.get_profile(profile_id)
    return jsonify({"profile": profile}), 201


@app.route("/api/profiles/<int:profile_id>", methods=["GET"])
def get_profile(profile_id):
    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"profile": profile})


@app.route("/api/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id):
    if not db.delete_profile(profile_id):
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/profiles/<int:profile_id>/sync", methods=["POST"])
def sync_profile(profile_id):
    """Re-fetch cards from CR API and update the profile."""
    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    if not clash_api.api_key:
        return jsonify({"error": "Clash Royale API key not configured on this server."}), 503

    result = clash_api.get_player_cards(profile["player_tag"])
    if "error" in result:
        return jsonify(result), 400

    player = result["player"]
    cards = _dedup_cards(result["cards"])
    db.update_profile_sync(
        profile_id=profile_id,
        player_name=player["name"],
        trophies=player["trophies"],
        arena=player["arena"],
        collection=cards,
    )

    # Sync battle log too
    battle_count = 0
    try:
        blog = clash_api.get_player_battlelog(profile["player_tag"])
        if "battles" in blog:
            battle_count = db.save_battles(profile_id, blog["battles"])
    except Exception:
        pass

    updated = db.get_profile(profile_id)
    return jsonify({"profile": updated, "new_battles": battle_count})


def _dedup_cards(cards: list) -> list:
    seen = set()
    result = []
    for c in cards:
        key = c["name"].lower()
        if key not in seen:
            seen.add(key)
            result.append({
                "name": c["name"],
                "level": c["level"],
                "maxLevel": c.get("maxLevel", 16),
                "elixirCost": c.get("elixirCost"),
                "rarity": c.get("rarity", ""),
            })
    return result


# ── Recommendation Analysis (streaming) ───────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def analyze_deck():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    cards = data.get("cards", [])
    profile_id = data.get("profile_id")
    if not cards:
        return jsonify({"error": "No cards provided"}), 400
    if len(cards) < 8:
        return jsonify({"error": "You need at least 8 cards to build a deck"}), 400

    # New optional parameters
    num_decks = min(max(int(data.get("num_decks", 3)), 1), 10)
    strategies = data.get("strategies") or None  # list of archetype strings or None
    selected_cards = data.get("selected_cards") or None  # list of card name strings or None

    player_tag = None
    previous_decks = None
    if profile_id:
        profile = db.get_profile(profile_id)
        if profile:
            player_tag = profile["player_tag"]
            # Get non-archived saved deck card lists to avoid duplicate recs
            active_decks = db.get_active_saved_deck_cards(profile_id)
            if active_decks:
                previous_decks = active_decks

    def generate():
        accumulated = ""
        usage_data = None
        try:
            for kind, value in deck_analyzer.analyze_stream(
                cards, player_tag=player_tag,
                num_decks=num_decks, strategies=strategies,
                selected_cards=selected_cards,
                previous_decks=previous_decks,
            ):
                if kind == "status":
                    yield f"data: {json.dumps({'status': value})}\n\n"
                elif kind == "usage":
                    usage_data = value
                else:
                    accumulated += value
                    yield f"data: {json.dumps({'chunk': value})}\n\n"

            save_info = {}
            try:
                j0, j1 = accumulated.find("{"), accumulated.rfind("}")
                if j0 != -1 and j1 != -1:
                    parsed = json.loads(accumulated[j0:j1 + 1])
                    save_info = db.save_session(
                        cards=cards,
                        meta_context=parsed.get("meta_context", ""),
                        decks=parsed.get("decks", []),
                        profile_id=profile_id,
                    )
                else:
                    print(f"[recommend] no JSON braces found in response ({len(accumulated)} chars): {accumulated[:200]!r}", flush=True)
            except Exception as e:
                print(f"[recommend] JSON parse failed ({len(accumulated)} chars): {e}\nraw: {accumulated[:300]!r}", flush=True)

            yield f"data: {json.dumps({'done': True, 'usage': usage_data, **save_info})}\n\n"
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
    profile_id = request.args.get("profile_id", type=int)
    return jsonify({"sessions": db.list_sessions(profile_id=profile_id)})


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

    player_tag = data.get("player_tag")
    history = db.get_chat_history(deck_id)
    db.save_chat_message(deck_id, "user", user_message)

    def generate():
        full_response = ""
        usage_data = None
        try:
            for kind, value in deck_analyzer.chat_stream(
                deck_data["deck"], deck_data["cards"], history, user_message,
                player_tag=player_tag,
            ):
                if kind == "status":
                    yield f"data: {json.dumps({'status': value})}\n\n"
                elif kind == "usage":
                    usage_data = value
                else:
                    full_response += value
                    yield f"data: {json.dumps({'chunk': value})}\n\n"
            db.save_chat_message(deck_id, "assistant", full_response)
            yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
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
    profile_id = request.args.get("profile_id", type=int)
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    return jsonify({"decks": db.list_saved_decks(profile_id=profile_id, include_archived=include_archived)})


@app.route("/api/saved-decks", methods=["POST"])
def create_saved_deck():
    data = request.get_json() or {}
    name = data.get("name", "My Deck").strip() or "My Deck"
    cards = data.get("cards", [])
    source = data.get("source", "manual")
    profile_id = data.get("profile_id")

    if len(cards) != 8:
        return jsonify({"error": "Deck must have exactly 8 cards"}), 400
    names = [c["name"] for c in cards]
    if len(names) != len(set(n.lower() for n in names)):
        return jsonify({"error": "Deck cannot contain duplicate cards"}), 400

    deck_id = db.create_saved_deck(name=name, cards=cards, source=source, profile_id=profile_id)
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
        db.clear_saved_deck_analysis(deck_id)

    if not db.update_saved_deck(deck_id, name=name, cards=cards):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/saved-decks/<int:deck_id>", methods=["DELETE"])
def delete_saved_deck(deck_id):
    if not db.delete_saved_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"ok": True})


# ── Saved Deck Analysis (streaming) ───────────────────────────────────────

@app.route("/api/saved-decks/<int:deck_id>/analysis", methods=["GET"])
def get_saved_deck_analysis(deck_id):
    if not db.get_saved_deck(deck_id):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify(db.get_saved_deck_analysis(deck_id) or {})


@app.route("/api/saved-decks/<int:deck_id>/analysis", methods=["PUT"])
def save_saved_deck_analysis_direct(deck_id):
    """Directly store an analysis dict without running AI (used to persist rec-deck results)."""
    deck = db.get_saved_deck(deck_id)
    if not deck:
        return jsonify({"error": "Deck not found"}), 404
    data = request.get_json() or {}
    analysis = data.get("analysis")
    collection_snapshot = data.get("collection", [])
    if not analysis:
        return jsonify({"error": "analysis is required"}), 400
    db.save_saved_deck_analysis(deck_id, analysis, collection_snapshot)
    return jsonify({"ok": True})


@app.route("/api/saved-decks/<int:deck_id>/analysis", methods=["POST"])
def run_saved_deck_analysis(deck_id):
    deck = db.get_saved_deck(deck_id)
    if not deck:
        return jsonify({"error": "Deck not found"}), 404

    data = request.get_json() or {}
    collection = data.get("collection", [])
    player_tag = data.get("player_tag")

    def generate():
        accumulated = ""
        usage_data = None
        try:
            for kind, value in deck_analyzer.analyze_saved_deck_stream(deck["cards"], collection, player_tag=player_tag):
                if kind == "status":
                    yield f"data: {json.dumps({'status': value})}\n\n"
                elif kind == "usage":
                    usage_data = value
                else:
                    accumulated += value
                    yield f"data: {json.dumps({'chunk': value})}\n\n"

            try:
                j0, j1 = accumulated.find("{"), accumulated.rfind("}")
                if j0 != -1 and j1 != -1:
                    parsed = json.loads(accumulated[j0:j1 + 1])
                    db.save_saved_deck_analysis(deck_id, parsed, collection)
                    yield f"data: {json.dumps({'done': True, 'analysis': parsed, 'usage': usage_data})}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
            except Exception:
                yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
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
    player_tag = data.get("player_tag")

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
        usage_data = None
        try:
            for kind, value in deck_analyzer.saved_deck_chat_stream(
                deck["cards"], analysis, collection, history, user_message,
                player_tag=player_tag,
            ):
                if kind == "status":
                    yield f"data: {json.dumps({'status': value})}\n\n"
                elif kind == "usage":
                    usage_data = value
                else:
                    full_response += value
                    yield f"data: {json.dumps({'chunk': value})}\n\n"
            db.append_saved_deck_chat(deck_id, "assistant", full_response)
            yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Deck Archiving ────────────────────────────────────────────────────────

@app.route("/api/saved-decks/<int:deck_id>/archive", methods=["POST"])
def toggle_archive_deck(deck_id):
    data = request.get_json() or {}
    archived = data.get("archived", True)
    if not db.archive_saved_deck(deck_id, archived):
        return jsonify({"error": "Deck not found"}), 404
    return jsonify({"ok": True, "archived": archived})


# ── Battle Log ────────────────────────────────────────────────────────────

@app.route("/api/profiles/<int:profile_id>/battles", methods=["GET"])
def list_battles(profile_id):
    if not db.get_profile(profile_id):
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"battles": db.list_battles(profile_id)})


@app.route("/api/profiles/<int:profile_id>/battles/sync", methods=["POST"])
def sync_battles(profile_id):
    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    if not clash_api.api_key:
        return jsonify({"error": "Clash Royale API key not configured."}), 503

    blog = clash_api.get_player_battlelog(profile["player_tag"])
    if "error" in blog:
        return jsonify(blog), 400
    count = db.save_battles(profile_id, blog["battles"])
    return jsonify({"new_battles": count, "battles": db.list_battles(profile_id)})


@app.route("/api/battles/<int:battle_id>/analysis", methods=["POST"])
def run_battle_analysis(battle_id):
    battle = db.get_battle(battle_id)
    if not battle:
        return jsonify({"error": "Battle not found"}), 404

    def generate():
        accumulated = ""
        usage_data = None
        try:
            for kind, value in deck_analyzer.analyze_battle_stream(battle):
                if kind == "status":
                    yield f"data: {json.dumps({'status': value})}\n\n"
                elif kind == "usage":
                    usage_data = value
                else:
                    accumulated += value
                    yield f"data: {json.dumps({'chunk': value})}\n\n"
            try:
                j0, j1 = accumulated.find("{"), accumulated.rfind("}")
                if j0 != -1 and j1 != -1:
                    parsed = json.loads(accumulated[j0:j1 + 1])
                    db.save_battle_analysis(battle_id, parsed)
                    yield f"data: {json.dumps({'done': True, 'analysis': parsed, 'usage': usage_data})}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
            except Exception:
                yield f"data: {json.dumps({'done': True, 'usage': usage_data})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=debug, port=port)
