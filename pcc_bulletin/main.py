import logging
import sys
from pathlib import Path

from .alerts import raise_alarm, warn_if_unconfigured
from .config import Config
from .failure_state import clear_config_error, clear_failure, failed_before, is_new_config_error
from .processor import process_bulletin
from .watcher import find_latest, find_unprocessed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> int:
    try:
        config = Config.from_env()
    except RuntimeError as exc:
        if is_new_config_error(str(exc)):
            raise_alarm(
                "CLAUDE API CAN'T BE CALLED: configuration error",
                f"pcc-bulletin could not start, so no bulletin email will be generated.\n\n{exc}",
            )
        else:
            # Same error as last run; already alerted. Don't loop on the watcher.
            log.critical("Still failing (already alerted): %s", exc)
        return 1

    clear_config_error()
    warn_if_unconfigured()

    if len(sys.argv) > 1 and sys.argv[1] == "--latest":
        # Force mode: newest bulletin in the folder, even if already processed
        pdfs = find_latest(config.bulletin_folder)
    elif len(sys.argv) > 1:
        # Explicit path — useful for manual re-runs or testing
        pdfs = [Path(sys.argv[1])]
    else:
        pdfs = []
        for pdf_path in find_unprocessed(config.bulletin_folder):
            if failed_before(pdf_path):
                # Don't loop: the error log append re-triggers the path watcher.
                log.warning(
                    "Skipping %s: its last Claude API call failed and the PDF hasn't changed. "
                    "Rerun by hand with ./force-run.sh or pcc-bulletin '%s'.",
                    pdf_path.name,
                    pdf_path,
                )
            else:
                pdfs.append(pdf_path)

    if not pdfs:
        log.info("No bulletins to process.")
        return 0

    exit_code = 0
    for pdf_path in pdfs:
        log.info("Processing %s", pdf_path.name)
        try:
            out_path = process_bulletin(pdf_path, config)
            log.info("Generated %s", out_path.name)
            clear_failure(pdf_path)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to process %s: %s", pdf_path.name, exc)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
