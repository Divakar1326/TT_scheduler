"""Configuration settings for the University Timetable Generation System."""
import os
import logging
from logging.handlers import RotatingFileHandler

# Load .env file manually into os.environ if present
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

# Required environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_SCHEMA = os.environ.get("DATABASE_SCHEMA", "public")
LOCAL_MODE = os.environ.get("LOCAL_MODE", "false").lower() == "true"
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "database", "timetable.db"))

# AI Providers Settings
AI_PROVIDER = os.environ.get("AI_PROVIDER", "openrouter").lower()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-coder:free")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "llama3.1-8b")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

SECRET_KEY = (os.environ.get("JWT_SECRET") or "dev_secret_key_timetable_system_123!").strip().strip("'\"")
APP_ENV = os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV", "production").lower()
FLASK_ENV = APP_ENV
port_env = os.environ.get("PORT")
PORT = int(port_env) if port_env and port_env.strip().isdigit() else 8000
GITHUB_URL = os.environ.get("GITHUB_URL", "https://github.com/Divakar1326")
LINKEDIN_URL = os.environ.get("LINKEDIN_URL", "https://www.linkedin.com/in/divakar1326/")

# Database timeout configurations
timeout_env = os.environ.get("DB_TIMEOUT_SECONDS")
DB_TIMEOUT_SECONDS = int(timeout_env) if timeout_env and timeout_env.strip().isdigit() else 10

# Logging Configuration
LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

# Initialize logger
logger = logging.getLogger("TT_Scheduler")
logger.setLevel(LOG_LEVEL)

# Console logger
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)

# Rotating File Handler for production (Daily Timestamped Rotating files)
from logging.handlers import TimedRotatingFileHandler
log_dir = os.path.join(BASE_DIR, "logs")
try:
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "timetable_app.log")
    file_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
except Exception as e:
    pass

# Helper to mask secret variables
def mask_secret(val: str) -> str:
    if not val:
        return "Not Set"
    if len(val) <= 8:
        return "***"
    return f"{val[:4]}...{val[-4:]}"

# Validation and Logging state
logger.info("Initializing environment configurations.")
logger.info(f"APP_ENV / FLASK_ENV: {APP_ENV}")
logger.info(f"LOCAL_MODE: {LOCAL_MODE}")
logger.info(f"PORT: {PORT}")
logger.info(f"DATABASE_PATH: {DATABASE_PATH}")
logger.info(f"DATABASE_SCHEMA: {DATABASE_SCHEMA}")
logger.info(f"AI_PROVIDER (Primary): {AI_PROVIDER}")
logger.info(f"OPENROUTER_MODEL: {OPENROUTER_MODEL}")
logger.info(f"GROQ_MODEL: {GROQ_MODEL}")
logger.info(f"CEREBRAS_MODEL: {CEREBRAS_MODEL}")
logger.info(f"GEMINI_MODEL: {GEMINI_MODEL}")

CONFIG_ERRORS = []

# Production variables validation
if not LOCAL_MODE:
    missing = []
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET") == "dev_secret_key_timetable_system_123!":
        missing.append("JWT_SECRET (Production requires secure JWT_SECRET environment variable)")
    
    if missing:
        error_msg = f"[ERROR] PRODUCTION CONFIGURATION ERROR: Missing required variables: {', '.join(missing)}. Or run with LOCAL_MODE=true for local SQLite development."
        logger.error(error_msg)
        CONFIG_ERRORS = missing

