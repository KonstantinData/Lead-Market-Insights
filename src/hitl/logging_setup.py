"""
Local rolling-file logging to ./log_storage without touching global log config.
"""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("./log_storage")
LOG_DIR.mkdir(parents=True, exist_ok=True)


_DEF_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"


# Explanation: create a dedicated logger that writes only to log_storage


def get_logger(name: str, filename: str) -> logging.Logger:
# Explanation: returns a logger with rotating handler (5 MB x 3)
logger = logging.getLogger(name)
logger.setLevel(logging.INFO)
logfile = LOG_DIR / filename
if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(logfile) for h in logger.handlers):
fh = RotatingFileHandler(str(logfile), maxBytes=5_000_000, backupCount=3, encoding="utf-8")
fh.setFormatter(logging.Formatter(_DEF_FMT))
logger.addHandler(fh)
logger.propagate = False
return logger