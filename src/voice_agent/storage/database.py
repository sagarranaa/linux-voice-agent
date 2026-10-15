import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Persist sessions and completed conversation exchanges."""

    def __init__(self, database_path: Path):
        database_path = Path(database_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(
            database_path,
            timeout=5.0,
        )

        self.connection.execute("PRAGMA foreign_keys = ON")

        with self.connection:
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    input_mode TEXT NOT NULL
                )
            """)

            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS exchanges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchanges_session
                ON exchanges(session_id, id)
            """)

    def start_session(self, input_mode: str) -> str:
        session_id = str(uuid4())

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO sessions (id, started_at, input_mode)
                VALUES (?, ?, ?)
                """,
                (session_id, utc_now(), input_mode),
            )

        return session_id

    def save_exchange(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO exchanges (
                    session_id,
                    created_at,
                    user_text,
                    assistant_text
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    utc_now(),
                    user_text,
                    assistant_text,
                ),
            )

    def end_session(self, session_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE sessions
                SET ended_at = ?
                WHERE id = ?
                """,
                (utc_now(), session_id),
            )

    def close(self) -> None:
        self.connection.close()