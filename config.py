"""Configuration settings for the University Timetable Generation System."""
import os
import logging
from logging.handlers import RotatingFileHandler

# Path to the SQLite database (read from environment or default to local directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "timetable.db"))

# Database timeout configurations
DB_TIMEOUT_SECONDS = int(os.environ.get("DB_TIMEOUT_SECONDS", 10))

# Load .env file manually into os.environ if present
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v

# Gemini Model settings
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Logging Configuration
LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Initialize logger
logger = logging.getLogger("TT_Scheduler")
logger.setLevel(LOG_LEVEL)

# Console logger
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)

# Rotating File Handler for production
log_file_path = os.path.join(BASE_DIR, "timetable_app.log")
try:
    file_handler = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
except Exception:
    # Fallback if log file cannot be created
    pass
