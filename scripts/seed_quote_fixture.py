from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/quote-fixture.sqlite3")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE transcript_segment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                text TEXT NOT NULL
            );
            CREATE TABLE chapter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL
            );
            CREATE TABLE quote (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                verified BOOLEAN NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO transcript_segment (episode_id, idx, text) VALUES (?, ?, ?)",
            ("episode-1", 0, "The verified quote appears exactly here."),
        )
        connection.execute("INSERT INTO chapter (id, episode_id) VALUES (?, ?)", (1, "episode-1"))
        connection.execute(
            "INSERT INTO quote (chapter_id, text, verified) VALUES (?, ?, ?)",
            (1, "verified quote appears exactly", 1),
        )
        connection.commit()
    print(f"Seeded quote fixture at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
