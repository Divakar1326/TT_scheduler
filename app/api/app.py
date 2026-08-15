"""Main Flask application config registering REST controllers."""
from flask import Flask, jsonify
from app.auth.auth import auth_bp
from app.api.crud import crud_bp
from app.api.scheduler_endpoints import scheduler_bp
from app.api.rules_endpoints import rules_bp
from app.api.hod_endpoints import hod_bp

from app.repository.startup_validator import run_startup_checks

_has_run_checks = False

def create_app() -> Flask:
    """Configures the Flask app and registers blueprints."""

    # Configure Flask to serve static files from app/static/ folder
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_folder = os.path.join(base_dir, "ui")
    
    app = Flask(__name__, static_folder=static_folder, static_url_path="")
    app.config["JSON_SORT_KEYS"] = False
    
    @app.before_request
    def check_startup():
        global _has_run_checks
        from config.config import CONFIG_ERRORS
        if CONFIG_ERRORS:
            raise RuntimeError(f"Production Configuration Error: Missing required environment variables: {', '.join(CONFIG_ERRORS)}")
        if not _has_run_checks:
            run_startup_checks()
            _has_run_checks = True
    
    # Root route serving index.html
    @app.route("/")
    def index():
        return app.send_static_file("index.html")
    
    # Global exception handler
    @app.errorhandler(Exception)
    def handle_exception(e):
        import uuid
        import datetime
        import logging
        request_id = str(uuid.uuid4())
        logging.getLogger("TT_Scheduler").error(
            f"[{request_id}] Unhandled exception: {e}", exc_info=True
        )
        return jsonify({
            "error": "An unexpected server error occurred. Please try again or contact support.",
            "request_id": request_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500
        
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(crud_bp, url_prefix="/api")
    app.register_blueprint(scheduler_bp, url_prefix="/api")
    app.register_blueprint(rules_bp, url_prefix="/api")
    app.register_blueprint(hod_bp, url_prefix="/api")
    
    return app

from config.config import PORT, FLASK_ENV

app = create_app()

if __name__ == "__main__":
    debug_mode = (FLASK_ENV == "development")
    app.run(host="0.0.0.0", port=PORT, debug=debug_mode)
