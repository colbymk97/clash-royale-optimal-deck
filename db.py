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
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                meta_context TEXT,
                cards_json   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                name       TEXT,
                archetype  TEXT,
                deck_json  TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id    INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


def save_session(cards: list, meta_context: str, decks: list) -> dict:
    """Persist a full analysis session. Returns {session_id, deck_ids}."""
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
    """Return recent sessions (summary only, newest first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.created_at, s.meta_context,
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
    """Return a full session with its decks (no chat messages)."""
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
    """Return a deck + its session's full card collection."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT d.id, d.session_id, d.deck_json, s.cards_json
            FROM decks d
            JOIN sessions s ON s.id = d.session_id
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
    """Return all chat messages for a deck, oldest first."""
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
