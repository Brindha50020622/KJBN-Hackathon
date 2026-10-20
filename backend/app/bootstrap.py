import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.logging_setup import setup_logging
from app.seed import seed_stores
from app.service import process_batch, register_upload

log = logging.getLogger("app.bootstrap")
HISTORY_FILE = Path(__file__).resolve().parent.parent / "seed_data" / "history_14days.csv"


def run_migrations() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


def load_history(path: Path) -> None:
    if not path.is_file():
        log.warning("history file not found", extra={"path": str(path)})
        return
    raw = path.read_bytes()
    batch, should_process = register_upload(path.name, raw)
    if not should_process:
        log.info("history already loaded", extra={"batch_id": batch.id})
        return
    process_batch(batch.id, raw, datetime.now(UTC), "bootstrap")


def main() -> None:
    setup_logging(settings.log_level)
    run_migrations()
    seed_stores()
    if settings.seed_history:
        load_history(HISTORY_FILE)


if __name__ == "__main__":
    main()
