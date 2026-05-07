from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from podsum.domain.quote_verifier import verify


def main() -> int:
    db_path = Path(os.environ.get("DB_PATH", "data/podsum.sqlite3"))
    if not db_path.exists():
        print(f"No database found at {db_path}; PASS 0 / FAIL 0")
        return 0

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT quote.id, quote.text, chapter.episode_id
            FROM quote
            JOIN chapter ON chapter.id = quote.chapter_id
            WHERE quote.verified = 1
            ORDER BY chapter.episode_id, quote.id
            """
        ).fetchall()

        pass_count = 0
        failures: list[tuple[int, str]] = []
        transcript_cache: dict[str, str] = {}
        for quote_id, quote_text, episode_id in rows:
            transcript = transcript_cache.get(episode_id)
            if transcript is None:
                transcript = _transcript_text(connection, episode_id)
                transcript_cache[episode_id] = transcript
            if verify(str(quote_text), transcript):
                pass_count += 1
            else:
                failures.append((int(quote_id), str(episode_id)))

    fail_count = len(failures)
    print(f"PASS {pass_count} / FAIL {fail_count}")
    for quote_id, episode_id in failures:
        print(f"FAIL quote_id={quote_id} episode_id={episode_id}")
    return 1 if failures else 0


def _transcript_text(connection: sqlite3.Connection, episode_id: str) -> str:
    rows = connection.execute(
        """
        SELECT text
        FROM transcript_segment
        WHERE episode_id = ?
        ORDER BY idx
        """,
        (episode_id,),
    ).fetchall()
    return "\n".join(str(row[0]) for row in rows)


if __name__ == "__main__":
    sys.exit(main())
