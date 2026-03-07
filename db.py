import sqlite3
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "decks.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _get_conn() as conn:
        conn.executescript("""
            -- Recommendation analysis sessions
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                meta_context TEXT,
                cards_json   TEXT NOT NULL
            );

            -- Recommendation decks (3 per session)
            CREATE TABLE IF NOT EXISTS decks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                name       TEXT,
                archetype  TEXT,
                deck_json  TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Chat for recommendation decks
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id    INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- User's saved/owned decks
            CREATE TABLE IF NOT EXISTS saved_decks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL DEFAULT 'My Deck',
                source     TEXT NOT NULL DEFAULT 'manual',
                cards_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- One-time deep analysis per saved deck (re-generated when cards change)
            CREATE TABLE IF NOT EXISTS saved_deck_analysis (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                saved_deck_id       INTEGER NOT NULL REFERENCES saved_decks(id) ON DELETE CASCADE,
                analysis_json       TEXT NOT NULL,
                collection_snapshot TEXT NOT NULL,
                created_at          TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Fine-tune chat per saved deck
            CREATE TABLE IF NOT EXISTS saved_deck_chat (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                saved_deck_id INTEGER NOT NULL REFERENCES saved_decks(id) ON DELETE CASCADE,
                role          TEXT NOT NULL,
                content       TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


# ── Recommendation Sessions ────────────────────────────────────────────────

def save_session(cards: list, meta_context: str, decks: list) -> dict:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (meta_context, cards_json) VALUES (?, ?)",
            (meta_context, json.dumps(cards)),
        )
        session_id = cur.lastrowid
        deck_ids = []
        for deck in decks:
            cur = conn.execute(
                "INSERT INTO decks (session_id, name, archetype, deck_json) VALUES (?, ?, ?, ?)",
                (session_id, deck.get("name", ""), deck.get("archetype", ""), json.dumps(deck)),
            )
            deck_ids.append(cur.lastrowid)
        return {"session_id": session_id, "deck_ids": deck_ids}


def list_sessions(limit: int = 30) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.created_at, s.meta_context,
                   s.cards_json,
                   COUNT(d.id) AS deck_count
            FROM sessions s
            LEFT JOIN decks d ON d.session_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_session(session_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        session = dict(row)
        session["cards"] = json.loads(session.pop("cards_json"))
        deck_rows = conn.execute(
            "SELECT * FROM decks WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        session["decks"] = [
            {**dict(d), "deck": json.loads(d["deck_json"])}
            for d in deck_rows
        ]
        return session


def get_deck(deck_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT d.id, d.session_id, d.deck_json, s.cards_json
            FROM decks d JOIN sessions s ON s.id = d.session_id
            WHERE d.id = ?
            """,
            (deck_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "deck": json.loads(row["deck_json"]),
            "cards": json.loads(row["cards_json"]),
        }


def get_chat_history(deck_id: int) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE deck_id = ? ORDER BY id",
            (deck_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_chat_message(deck_id: int, role: str, content: str):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (deck_id, role, content) VALUES (?, ?, ?)",
            (deck_id, role, content),
        )


# ── Saved Decks ────────────────────────────────────────────────────────────

def create_saved_deck(name: str, cards: list, source: str = "manual") -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO saved_decks (name, source, cards_json) VALUES (?, ?, ?)",
            (name, source, json.dumps(cards)),
        )
        return cur.lastrowid


def list_saved_decks() -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, source, cards_json, created_at, updated_at FROM saved_decks ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["cards"] = json.loads(d.pop("cards_json"))
            result.append(d)
        return result


def get_saved_deck(deck_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, source, cards_json, created_at, updated_at FROM saved_decks WHERE id = ?",
            (deck_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["cards"] = json.loads(d.pop("cards_json"))
        return d


def update_saved_deck(deck_id: int, name: str | None = None, cards: list | None = None) -> bool:
    sets = ["updated_at = datetime('now')"]
    params = []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if cards is not None:
        sets.append("cards_json = ?")
        params.append(json.dumps(cards))
    params.append(deck_id)
    with _get_conn() as conn:
        cur = conn.execute(
            f"UPDATE saved_decks SET {', '.join(sets)} WHERE id = ?", params
        )
        return cur.rowcount > 0


def delete_saved_deck(deck_id: int) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM saved_decks WHERE id = ?", (deck_id,))
        return cur.rowcount > 0


# ── Saved Deck Analysis ────────────────────────────────────────────────────

def get_saved_deck_analysis(saved_deck_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT analysis_json, collection_snapshot, created_at
            FROM saved_deck_analysis WHERE saved_deck_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (saved_deck_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "analysis": json.loads(row["analysis_json"]),
            "collection_snapshot": json.loads(row["collection_snapshot"]),
            "created_at": row["created_at"],
        }


def save_saved_deck_analysis(saved_deck_id: int, analysis: dict, collection_snapshot: list):
    with _get_conn() as conn:
        # Delete any prior analysis (only one stored at a time)
        conn.execute("DELETE FROM saved_deck_analysis WHERE saved_deck_id = ?", (saved_deck_id,))
        conn.execute(
            "INSERT INTO saved_deck_analysis (saved_deck_id, analysis_json, collection_snapshot) VALUES (?, ?, ?)",
            (saved_deck_id, json.dumps(analysis), json.dumps(collection_snapshot)),
        )


def clear_saved_deck_analysis(saved_deck_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM saved_deck_analysis WHERE saved_deck_id = ?", (saved_deck_id,))
        # Also clear chat so it can restart fresh after card changes
        conn.execute("DELETE FROM saved_deck_chat WHERE saved_deck_id = ?", (saved_deck_id,))


# ── Saved Deck Chat ────────────────────────────────────────────────────────

def get_saved_deck_chat(saved_deck_id: int) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM saved_deck_chat WHERE saved_deck_id = ? ORDER BY id",
            (saved_deck_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def append_saved_deck_chat(saved_deck_id: int, role: str, content: str):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO saved_deck_chat (saved_deck_id, role, content) VALUES (?, ?, ?)",
            (saved_deck_id, role, content),
        )
