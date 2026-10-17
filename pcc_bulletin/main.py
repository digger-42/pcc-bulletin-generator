import logging
import sys
from pathlib import Path

from .config import Config
from .processor import process_bulletin
from .watcher import find_unprocessed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> int:
    try:
        config = Config.from_env()
    except RuntimeError as exc:
        log.error(str(exc))
        return 1

    if len(sys.argv) > 1:
        # Explicit path — useful for manual re-runs or testing
        pdfs = [Path(sys.argv[1])]
    else:
        pdfs = find_unprocessed(config.bulletin_folder)

    if not pdfs:
        log.info("No unprocessed bulletins found.")
        return 0

    exit_code = 0
    for pdf_path in pdfs:
        log.info("Processing %s", pdf_path.name)
        try:
            out_path = process_bulletin(pdf_path, config)
            log.info("Generated %s", out_path.name)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to process %s: %s", pdf_path.name, exc)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
