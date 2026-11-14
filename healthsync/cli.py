"""Command-line helpers.  Example:  flask --app app create-user admin@example.com "Jane Admin" --role superadmin"""
import click
from werkzeug.security import generate_password_hash
from .constants import ROLES
from .db import q, run
from .validation import pw_error


def init_app(app):
    @app.cli.command("create-user")
    @click.argument("email")
    @click.argument("name")
    @click.option("--role", type=click.Choice(ROLES), default="superadmin", show_default=True)
    @click.password_option()
    def create_user(email, name, role, password):
        """Create a user (use this for the first super admin when demo data is off)."""
        email = email.strip().lower()
        if pw_error(password):
            raise click.ClickException(pw_error(password))
        if q("SELECT 1 FROM users WHERE email=?", (email,), one=True):
            raise click.ClickException("A user with that email already exists.")
        uid = run("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", (name, email, generate_password_hash(password), role))
        if role == "patient":
            run("INSERT INTO patients(user_id,name) VALUES(?,?)", (uid, name))
        click.echo(f"Created {role} {email}")
