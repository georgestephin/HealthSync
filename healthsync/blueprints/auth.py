import secrets
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from ..constants import GENDERS, PHONE
from ..db import q, run
from ..demo_data import demo_groups
from ..validation import prep, pw_error, validate

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = q("SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            if not user["active"]:
                flash("This account is disabled. Contact the HealthSync administrator.", "error")
            else:
                session.clear()
                session["uid"], session["csrf"] = user["id"], secrets.token_hex(16)
                nxt = request.form.get("next") or ""
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard.index"))
        else:
            flash("Email or password is incorrect.", "error")
    fields = [dict(name="email", label="Email", type="email", autocomplete="username"),
              dict(name="password", label="Password", type="password", autocomplete="current-password")]
    return render_template("auth.html", title="Log in", fields=prep(fields), vals={}, errs={}, submit="Log in",
                           next=request.args.get("next", ""), alt=("New patient?", "Create an account", url_for("auth.register")),
                           demo_groups=demo_groups() if current_app.config["SEED_DEMO_DATA"] else None)


@bp.route("/register", methods=["GET", "POST"])
def register():
    fields = [dict(name="name", label="Full name", minlength=2), dict(name="email", label="Email", type="email", autocomplete="email"),
              dict(name="phone", label="Phone", type="tel", **PHONE), dict(name="age", label="Age", type="number", max=120),
              dict(name="gender", label="Gender", type="select", options=GENDERS),
              dict(name="password", label="Password", type="password", autocomplete="new-password", minlength=8,
                   hint="Use at least 8 characters with a letter and a number."),
              dict(name="confirm", label="Confirm password", type="password", autocomplete="new-password", match="password")]
    vals, errs = {}, {}
    if request.method == "POST":
        vals, errs = validate(fields, request.form)
        if not errs:
            vals["email"] = vals["email"].lower()
            if pw_error(vals["password"]):
                errs["password"] = pw_error(vals["password"])
            elif vals["password"] != vals["confirm"]:
                errs["confirm"] = "Passwords do not match."
            elif q("SELECT 1 FROM users WHERE email=?", (vals["email"],), one=True):
                errs["email"] = "An account with this email already exists."
        if not errs:
            uid = run("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'patient')",
                      (vals["name"], vals["email"], generate_password_hash(vals["password"])))
            run("INSERT INTO patients(user_id,name,age,gender,phone) VALUES(?,?,?,?,?)",
                (uid, vals["name"], vals["age"], vals["gender"], vals["phone"]))
            flash("Account created. You can log in now.", "ok")
            return redirect(url_for("auth.login"))
        vals.pop("password", None)
        vals.pop("confirm", None)
    return render_template("auth.html", title="Create a patient account", fields=prep(fields), vals=vals, errs=errs,
                           submit="Create account", alt=("Already registered?", "Log in", url_for("auth.login")))


@bp.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.index"))
