import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.getLogger("gitbot").setLevel(logging.CRITICAL)
for name in ("webhook", "handler", "tg", "state", "authors"):
    logging.getLogger(f"gitbot.{name}").setLevel(logging.CRITICAL)
