from flask import Flask
from .models import init_db, ensure_csv_synced


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_PATH="receipts.db",
        CSV_PATH="receipts.csv",
        IMAGE_DIR="app/captured_receipts",
        SECRET_KEY="change-me",
    )

    if test_config:
        app.config.update(test_config)

    # Initialize persistence layer
    init_db(app.config["DATABASE_PATH"])
    ensure_csv_synced(app.config["DATABASE_PATH"], app.config["CSV_PATH"])

    from .main import bp as main_bp

    app.register_blueprint(main_bp)

    return app
