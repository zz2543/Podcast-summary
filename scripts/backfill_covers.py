"""Fetch cover images for video episodes ingested before covers were saved.

Run from the repository root, against the same DATA_DIR / DB_PATH the server
uses:

    PYTHONPATH=backend/src python scripts/backfill_covers.py [--dry-run]

It only adds ``cover.jpg`` next to each episode's audio; nothing else in the
episode directory or the database is touched. Episodes that already have a
cover are skipped, so re-running it only retries the ones that failed.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from podsum.config import get_settings
from podsum.persistence.models import Episode
from podsum.services import cover as cover_images
from podsum.services.ingest import fetch_video_cover


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="list what would be fetched")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between lookups")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        episodes = session.scalars(
            select(Episode).where(Episode.source_type == "youtube").order_by(Episode.created_at)
        ).all()
        todo = [
            (episode.id, episode.source_ref, Path(episode.data_dir))
            for episode in episodes
            if not cover_images.cover_path(Path(episode.data_dir)).is_file()
        ]

    print(f"{len(todo)} of {len(episodes)} video episodes have no cover")
    saved = 0
    for index, (episode_id, url, episode_dir) in enumerate(todo, start=1):
        if not episode_dir.is_dir():
            print(f"[{index}/{len(todo)}] {episode_id}: no episode directory, skipped")
            continue
        if args.dry_run:
            print(f"[{index}/{len(todo)}] {episode_id}: would fetch {url}")
            continue
        try:
            path = fetch_video_cover(url, episode_dir, settings)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            path = None
            print(f"[{index}/{len(todo)}] {episode_id}: lookup failed: {exc}")
        else:
            print(f"[{index}/{len(todo)}] {episode_id}: {'saved' if path else 'no cover found'}")
        saved += path is not None
        time.sleep(args.delay)
    if not args.dry_run:
        print(f"saved {saved} cover(s)")


if __name__ == "__main__":
    main()
