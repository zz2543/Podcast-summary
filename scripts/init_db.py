from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from podsum.config import get_settings


def main() -> None:
    settings = get_settings()
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    config = Config(str(Path("backend/alembic.ini")))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
