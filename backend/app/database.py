
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from app.config import DATABASE_URL


def get_db_path():
    if not DATABASE_URL.startswith("sqlite:///"):
        raise ValueError("Only SQLite DATABASE_URL is supported")

    path = DATABASE_URL[len("sqlite:///"):]

    if path.startswith("/"):
        return Path(path)

    return Path(__file__).resolve().parents[1] / path


DB_PATH = get_db_path()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(DB_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")

    return connection


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES sessions(session_id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, id)
        """)


def create_session(session_id, system_prompt):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions
            (session_id, system_prompt, created_at)
            VALUES (?, ?, ?)
            """,
            (session_id, system_prompt, now_iso())
        )


def get_session(session_id):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()


def update_system_prompt(session_id, system_prompt):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET system_prompt = ?
            WHERE session_id = ?
            """,
            (system_prompt, session_id)
        )


def get_messages(session_id):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT role, content, metadata, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,)
        ).fetchall()


def save_message(session_id, role, content, metadata=None):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages
            (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, metadata, now_iso())
        )



def list_sessions():
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                s.session_id,
                s.created_at,

                (
                    SELECT m.content
                    FROM messages m
                    WHERE m.session_id = s.session_id
                      AND m.role = 'user'
                    ORDER BY m.id ASC
                    LIMIT 1
                ) AS title,

                (
                    SELECT m.content
                    FROM messages m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message,

                (
                    SELECT COUNT(*)
                    FROM messages m
                    WHERE m.session_id = s.session_id
                ) AS message_count

            FROM sessions s

            WHERE EXISTS (
                SELECT 1
                FROM messages m
                WHERE m.session_id = s.session_id
                  AND m.role = 'user'
            )

            ORDER BY (
                SELECT MAX(m.id)
                FROM messages m
                WHERE m.session_id = s.session_id
            ) DESC
        """).fetchall()
