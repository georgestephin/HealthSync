"""Generic list + add/edit/delete pages for patients, doctors, inventory and beds.
Each page is described by a config dict in CONFIG; one view function serves them all."""
import sqlite3
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from ..constants import ADMINS, BLOOD_GROUPS, GENDERS, PHONE, SPECIALTIES, STAFF, SUPERADMIN
from ..db import q, run
from ..security import current_user
from ..validation import prep, pw_error, validate

bp = Blueprint("records", __name__)


def doctor_logins():
    return [(r["id"], f'{r["name"]} ({r["email"]})') for r in q("SELECT id,name,email FROM users WHERE role='doctor' ORDER BY name")]


def check_doctor(v, rid):
    errs = {}
    if v.get("user_id") and q("SELECT 1 FROM doctors WHERE user_id=? AND id IS NOT ?", (v["user_id"], rid), one=True):
        errs["user_id"] = "That login is already linked to another doctor profile."
    email, password = (v.get("login_email") or "").lower(), v.get("login_password") or ""
    if email or password:
        if not email:
            errs["login_email"] = "Enter the login email, or clear the password."
        elif q("SELECT 1 FROM users WHERE email=?", (email,), one=True):
            errs["login_email"] = "An account with this email already exists."
        if not password:
            errs["login_password"] = "Enter a temporary password for the login."
        elif pw_error(password):
            errs["login_password"] = pw_error(password)
    return errs


def after_doctor(v, doctor_id):
    """Create the doctor's login in the same step when an email and password were given."""
    if v.get("login_email"):
        uid = run("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'doctor')",
                  (v["name"], v["login_email"].lower(), generate_password_hash(v["login_password"])))
        run("UPDATE doctors SET user_id=? WHERE id=?", (uid, doctor_id))


def check_beds(v, rid):
    return {"occupied": "Occupied beds cannot exceed total beds."} if v["occupied"] > v["total"] else {}


# view: roles that may open the page (None = public); write: roles that may add/edit; delete: roles that may delete
CONFIG = {
    "patients": dict(title="Patient records", intro="Add, update and search patient records.", table="patients",
        view=SUPERADMIN, write=SUPERADMIN, delete=SUPERADMIN, form_title="Add a patient", submit="Add patient", empty="No patients yet. Add the first record using the form.",
        sql="SELECT * FROM patients ORDER BY id DESC",
        cols=[("Name", "name"), ("Age", "age"), ("Gender", "gender"), ("Phone", "phone"), ("Blood", "blood_group"), ("History", "history")],
        fields=[dict(name="name", label="Full name", minlength=2), dict(name="age", label="Age", type="number", max=120),
                dict(name="gender", label="Gender", type="select", options=GENDERS), dict(name="phone", label="Phone", type="tel", **PHONE),
                dict(name="blood_group", label="Blood group", type="select", options=BLOOD_GROUPS, required=False),
                dict(name="address", label="Address", required=False), dict(name="history", label="Medical history", type="textarea", required=False)]),
    "doctors": dict(title="Our doctors", intro="Specialists available for consultation.", table="doctors",
        view=None, write=ADMINS, delete=ADMINS, form_title="Add a doctor", submit="Add doctor", empty="No doctor profiles yet.",
        sql="SELECT d.*, u.email AS login FROM doctors d LEFT JOIN users u ON u.id=d.user_id ORDER BY d.specialty, d.name",
        cols=[("Name", "name"), ("Specialty", "specialty"), ("Available", "available_days"), ("Fee (₹)", "fee")],
        staff_cols=[("Login", "login")],
        fields=[dict(name="name", label="Doctor name", minlength=3), dict(name="specialty", label="Specialty", type="select", options=SPECIALTIES),
                dict(name="phone", label="Phone", type="tel", required=False, **PHONE), dict(name="fee", label="Consultation fee (₹)", type="number", max=20000),
                dict(name="available_days", label="Available days", required=False),
                dict(name="login_email", label="Login email (optional)", type="email", required=False, virtual=True, show="create", autocomplete="off"),
                dict(name="login_password", label="Temporary password", type="password", required=False, virtual=True, show="create",
                     minlength=8, hint="Use at least 8 characters with a letter and a number.", autocomplete="new-password"),
                dict(name="user_id", label="Linked doctor login", type="select", options=doctor_logins, required=False, show="edit")],
        check=check_doctor, after=after_doctor),
    "inventory": dict(title="Medicines & supplies", intro="Track stock levels. Items at or below their reorder level are flagged.", table="inventory",
        view=ADMINS, write=ADMINS, delete=ADMINS, form_title="Add an item", submit="Add item", empty="Inventory is empty.",
        sql="SELECT *, CASE WHEN qty<=reorder_level THEN 'Low' ELSE 'OK' END AS status FROM inventory ORDER BY (qty<=reorder_level) DESC, item",
        cols=[("Item", "item"), ("Category", "category"), ("In stock", "qty"), ("Unit", "unit"), ("Reorder at", "reorder_level"), ("Status", "status")],
        badges={"status"},
        fields=[dict(name="item", label="Item name"), dict(name="category", label="Category", type="select", options=["Medicine", "Supplies", "Equipment"]),
                dict(name="qty", label="Quantity in stock", type="number"), dict(name="unit", label="Unit (e.g. strips, boxes)"),
                dict(name="reorder_level", label="Reorder level", type="number")]),
    "beds": dict(title="Bed availability", intro="Live ward occupancy, so you know before you travel.", table="beds",
        view=None, write=STAFF, delete=ADMINS, form_title="Add a ward", submit="Add ward", empty="No wards configured.",
        sql="SELECT *, total-occupied AS free, CASE WHEN total=occupied THEN 'Full' WHEN (total-occupied)*5<=total THEN 'Limited' ELSE 'Available' END AS status FROM beds ORDER BY ward",
        cols=[("Ward", "ward"), ("Total beds", "total"), ("Occupied", "occupied"), ("Free", "free"), ("Status", "status")], badges={"status"},
        fields=[dict(name="ward", label="Ward name"), dict(name="total", label="Total beds", type="number", min=1, max=500),
                dict(name="occupied", label="Occupied beds", type="number", max=500)], check=check_beds),
}


def records_view(key):
    cfg, user = CONFIG[key], current_user()
    if cfg["view"] and (not user or user["role"] not in cfg["view"]):
        if not user:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        abort(403)
    can_write = bool(user and user["role"] in cfg["write"])
    can_delete = bool(user and user["role"] in cfg["delete"])
    vals, errs, edit_id = {}, {}, request.args.get("edit", type=int)
    rid = request.form.get("id", type=int) if request.method == "POST" else None
    editing = bool(rid or (edit_id and can_write))
    fields = [f for f in cfg["fields"] if f.get("show") in (None, "edit" if editing else "create")]

    if request.method == "POST":
        if not can_write:
            abort(403)
        if request.form.get("_action") == "delete":
            if not can_delete:
                abort(403)
            run(f"DELETE FROM {cfg['table']} WHERE id=?", (rid,))
            flash("Record deleted.", "ok")
            return redirect(request.path)
        vals, errs = validate(fields, request.form)
        if not errs and cfg.get("check"):
            errs.update(cfg["check"](vals, rid))
        if not errs:
            names = [f["name"] for f in fields if not f.get("virtual")]
            try:
                if rid:
                    run(f"UPDATE {cfg['table']} SET {','.join(x + '=?' for x in names)} WHERE id=?", [vals[x] for x in names] + [rid])
                    saved_id = rid
                else:
                    saved_id = run(f"INSERT INTO {cfg['table']}({','.join(names)}) VALUES({','.join('?' * len(names))})", [vals[x] for x in names])
                if cfg.get("after"):
                    cfg["after"](vals, saved_id)
                flash("Saved successfully.", "ok")
                return redirect(request.path)
            except sqlite3.IntegrityError:
                flash("That entry already exists.", "error")
        edit_id = rid
    elif edit_id and can_write:
        vals = dict(q(f"SELECT * FROM {cfg['table']} WHERE id=?", (edit_id,), one=True) or {})

    rows = [dict(r) for r in q(cfg["sql"])]
    for r in rows:
        r["acts"] = ([dict(label="Edit", url=f"?edit={r['id']}")] if can_write else []) + \
                    ([dict(label="Delete", action="delete", kind="danger", confirm="Delete this record permanently?")] if can_delete else [])
    cols = cfg["cols"] + (cfg.get("staff_cols", []) if user and user["role"] in STAFF else [])
    page = dict(cfg, cols=cols, show_form=can_write, rows=rows, fields=prep(fields), badges=cfg.get("badges", set()))
    return render_template("crud.html", c=page, vals=vals, errs=errs, edit_id=edit_id, ward_cards=rows if key == "beds" else None)


def _make_view(key):
    return lambda: records_view(key)


for _key in CONFIG:
    bp.add_url_rule(f"/{_key}", _key, _make_view(_key), methods=["GET", "POST"])
