"""
Version console (sans interface).
Lit la configuration depuis le fichier .env. Utile pour le debogage ou un
lancement automatise. L'interface graphique est dans scriba_gui.py.

Usage : python scriba.py [dossier_a_surveiller]
"""

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from scan_engine import DEFAULT_PRESET, ScanEngine, build_prompt, preset_style
from version import __version__, APP_NAME

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent

load_dotenv(APP_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(APP_DIR / "scriba.log", encoding="utf-8"),
    ],
)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("scriba")

_LEVELS = {"info": logging.INFO, "warn": logging.WARNING,
           "error": logging.ERROR, "success": logging.INFO}


def engine_log(msg: str, level: str = "info") -> None:
    log.log(_LEVELS.get(level, logging.INFO), msg)


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "oui")


def main() -> int:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.error("GEMINI_API_KEY manquante. Renseigne-la dans le fichier .env.")
        return 1

    model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip()
    preset = os.getenv("NAMING_PRESET", DEFAULT_PRESET).strip() or DEFAULT_PRESET
    if len(sys.argv) > 1:
        watch_dir = Path(sys.argv[1]).expanduser()
    else:
        wd = os.getenv("WATCH_DIR", "").strip()
        watch_dir = Path(wd).expanduser() if wd else APP_DIR / "scans"

    engine = ScanEngine(api_key, model, watch_dir, dry_run=_flag("DRY_RUN"),
                        log=engine_log,
                        prompt=build_prompt(preset_style(preset)))

    print("=" * 64)
    print(f"  {APP_NAME} v{__version__} - console  (Ctrl+C pour quitter)")
    print("=" * 64)
    engine.start()
    if _flag("SCAN_EXISTING"):
        engine.scan_existing()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Arrêt demandé.")
    finally:
        engine.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
