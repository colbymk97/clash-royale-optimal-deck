from __future__ import annotations
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
            -- Player profiles
            CREATE TABLE IF NOT EXISTS profiles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag      TEXT NOT NULL UNIQUE,
                player_name     TEXT NOT NULL DEFAULT '',
                trophies        INTEGER DEFAULT 0,
                arena           TEXT DEFAULT '',
                collection_json TEXT NOT NULL DEFAULT '[]',
                last_synced     TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Recommendation analysis sessions
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id   INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
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
                profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
                name       TEXT NOT NULL DEFAULT 'My Deck',
                source     TEXT NOT NULL DEFAULT 'manual',
                cards_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- One-time deep analysis per saved deck
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

            -- Battle log
            CREATE TABLE IF NOT EXISTS battles (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id       INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                battle_time      TEXT NOT NULL,
                game_mode        TEXT DEFAULT '',
                arena            TEXT DEFAULT '',
                result           TEXT NOT NULL,
                team_crowns      INTEGER DEFAULT 0,
                opponent_crowns  INTEGER DEFAULT 0,
                team_cards_json  TEXT NOT NULL,
                opponent_name    TEXT DEFAULT '',
                opponent_tag     TEXT DEFAULT '',
                opponent_trophies INTEGER DEFAULT 0,
                opponent_cards_json TEXT NOT NULL,
                analysis_json    TEXT,
                created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(profile_id, battle_time)
            );
        """)

    # Migrate pre-profile tables: add columns if missing
    with _get_conn() as conn:
        for table, col_def in [
            ("sessions",    "profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL"),
            ("saved_decks", "profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE"),
            ("saved_decks", "archived INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except Exception:
                pass  # column already exists


# ── Profiles ───────────────────────────────────────────────────────────────

def list_profiles() -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, player_tag, player_name, trophies, arena, last_synced, created_at "
            "FROM profiles ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_profile(profile_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, player_tag, player_name, trophies, arena, collection_json, last_synced "
            "FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["collection"] = json.loads(d.pop("collection_json"))
        return d


def create_profile(player_tag: str, player_name: str, trophies: int, arena: str, collection: list) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (player_tag, player_name, trophies, arena, collection_json, last_synced) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (player_tag.upper(), player_name, trophies, arena, json.dumps(collection)),
        )
        return cur.lastrowid


def update_profile_sync(profile_id: int, player_name: str, trophies: int, arena: str, collection: list):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE profiles SET player_name=?, trophies=?, arena=?, collection_json=?, last_synced=datetime('now') "
            "WHERE id=?",
            (player_name, trophies, arena, json.dumps(collection), profile_id),
        )


def delete_profile(profile_id: int) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cur.rowcount > 0


def get_profile_by_tag(player_tag: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM profiles WHERE player_tag = ?", (player_tag.upper(),)
        ).fetchone()
        return dict(row) if row else None


# ── Recommendation Sessions ────────────────────────────────────────────────

def save_session(cards: list, meta_context: str, decks: list, profile_id: int | None = None) -> dict:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (profile_id, meta_context, cards_json) VALUES (?, ?, ?)",
            (profile_id, meta_context, json.dumps(cards)),
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


def list_sessions(limit: int = 30, profile_id: int | None = None) -> list:
    with _get_conn() as conn:
        if profile_id is not None:
            rows = conn.execute(
                """
                SELECT s.id, s.created_at, s.meta_context, s.cards_json,
                       COUNT(d.id) AS deck_count
                FROM sessions s
                LEFT JOIN decks d ON d.session_id = s.id
                WHERE s.profile_id = ?
                GROUP BY s.id ORDER BY s.id DESC LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT s.id, s.created_at, s.meta_context, s.cards_json,
                       COUNT(d.id) AS deck_count
                FROM sessions s
                LEFT JOIN decks d ON d.session_id = s.id
                GROUP BY s.id ORDER BY s.id DESC LIMIT ?
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

def create_saved_deck(name: str, cards: list, source: str = "manual", profile_id: int | None = None) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO saved_decks (profile_id, name, source, cards_json) VALUES (?, ?, ?, ?)",
            (profile_id, name, source, json.dumps(cards)),
        )
        return cur.lastrowid


def list_saved_decks(profile_id: int | None = None, include_archived: bool = False) -> list:
    with _get_conn() as conn:
        archive_filter = "" if include_archived else " AND archived = 0"
        if profile_id is not None:
            rows = conn.execute(
                "SELECT id, name, source, cards_json, created_at, updated_at, archived "
                f"FROM saved_decks WHERE profile_id = ?{archive_filter} ORDER BY updated_at DESC",
                (profile_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, source, cards_json, created_at, updated_at, archived "
                f"FROM saved_decks WHERE 1=1{archive_filter} ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["cards"] = json.loads(d.pop("cards_json"))
            d["archived"] = bool(d.get("archived", 0))
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
            "SELECT analysis_json, collection_snapshot, created_at "
            "FROM saved_deck_analysis WHERE saved_deck_id = ? ORDER BY id DESC LIMIT 1",
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
        conn.execute("DELETE FROM saved_deck_analysis WHERE saved_deck_id = ?", (saved_deck_id,))
        conn.execute(
            "INSERT INTO saved_deck_analysis (saved_deck_id, analysis_json, collection_snapshot) VALUES (?, ?, ?)",
            (saved_deck_id, json.dumps(analysis), json.dumps(collection_snapshot)),
        )


def clear_saved_deck_analysis(saved_deck_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM saved_deck_analysis WHERE saved_deck_id = ?", (saved_deck_id,))
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


# ── Deck Archiving ────────────────────────────────────────────────────────

def archive_saved_deck(deck_id: int, archived: bool = True) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE saved_decks SET archived = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if archived else 0, deck_id),
        )
        return cur.rowcount > 0


def get_active_saved_deck_cards(profile_id: int) -> list[list[str]]:
    """Return card name lists for all non-archived saved decks for a profile."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT cards_json FROM saved_decks WHERE profile_id = ? AND archived = 0",
            (profile_id,),
        ).fetchall()
        result = []
        for r in rows:
            cards = json.loads(r["cards_json"])
            result.append(sorted(c["name"] for c in cards))
        return result


# ── Battle Log ────────────────────────────────────────────────────────────

def save_battles(profile_id: int, battles: list[dict]) -> int:
    """Insert battles, skipping duplicates. Returns count of new battles."""
    inserted = 0
    with _get_conn() as conn:
        for b in battles:
            try:
                conn.execute(
                    """INSERT INTO battles
                       (profile_id, battle_time, game_mode, arena, result,
                        team_crowns, opponent_crowns, team_cards_json,
                        opponent_name, opponent_tag, opponent_trophies, opponent_cards_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        profile_id,
                        b["battleTime"],
                        b.get("gameMode", ""),
                        b.get("arena", ""),
                        b["result"],
                        b.get("team_crowns", 0),
                        b.get("opponent_crowns", 0),
                        json.dumps(b.get("team_cards", [])),
                        b.get("opponent_name", ""),
                        b.get("opponent_tag", ""),
                        b.get("opponent_trophies", 0),
                        json.dumps(b.get("opponent_cards", [])),
                    ),
                )
                inserted += 1
            except Exception:
                pass  # duplicate battle_time
    return inserted


def list_battles(profile_id: int, limit: int = 50) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT id, battle_time, game_mode, arena, result,
                      team_crowns, opponent_crowns, team_cards_json,
                      opponent_name, opponent_tag, opponent_trophies,
                      opponent_cards_json, analysis_json
               FROM battles WHERE profile_id = ?
               ORDER BY battle_time DESC LIMIT ?""",
            (profile_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["team_cards"] = json.loads(d.pop("team_cards_json"))
            d["opponent_cards"] = json.loads(d.pop("opponent_cards_json"))
            d["analysis"] = json.loads(d["analysis_json"]) if d["analysis_json"] else None
            del d["analysis_json"]
            result.append(d)
        return result


def get_battle(battle_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT id, profile_id, battle_time, game_mode, arena, result,
                      team_crowns, opponent_crowns, team_cards_json,
                      opponent_name, opponent_tag, opponent_trophies,
                      opponent_cards_json, analysis_json
               FROM battles WHERE id = ?""",
            (battle_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["team_cards"] = json.loads(d.pop("team_cards_json"))
        d["opponent_cards"] = json.loads(d.pop("opponent_cards_json"))
        d["analysis"] = json.loads(d["analysis_json"]) if d["analysis_json"] else None
        del d["analysis_json"]
        return d


def save_battle_analysis(battle_id: int, analysis: dict):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE battles SET analysis_json = ? WHERE id = ?",
            (json.dumps(analysis), battle_id),
        )
