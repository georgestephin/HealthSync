"""HealthSync application package (app factory)."""
import os
from flask import Flask
from .config import Config


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.setdefault("DATABASE", os.path.join(app.instance_path, "healthsync.db"))

    from . import cli, db, hooks
    db.init_app(app)
    hooks.init_app(app)
    cli.init_app(app)

    from .blueprints import admin, appointments, auth, claims, dashboard, feedback, public, queueing, records
    for module in (public, auth, dashboard, appointments, queueing, claims, feedback, records, admin):
        app.register_blueprint(module.bp)

    with app.app_context():
        db.init_db()
    return app
