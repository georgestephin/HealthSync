import calendar
from datetime import date
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash
from ..constants import ADMINS, DEPT_COLORS, ROLES
from .. import charts as charts_lib
from ..db import n, q, run
from ..security import current_user, login_required
from ..validation import prep, pw_error, validate

bp = Blueprint("admin", __name__)


@bp.route("/users", methods=["GET", "POST"])
@login_required(*ADMINS)
def users():
    me = current_user()
    is_super = me["role"] == "superadmin"
    assignable = ROLES if is_super else ("patient", "doctor")
    fields = [dict(name="name", label="Full name", minlength=2), dict(name="email", label="Email", type="email"),
              dict(name="password", label="Temporary password", type="password", minlength=8, hint="Use at least 8 characters with a letter and a number."),
              dict(name="role", label="Role", type="select", options=list(assignable))]
    vals, errs = {}, {}
    if request.method == "POST":
        if request.form.get("_action") == "update":
            target = q("SELECT * FROM users WHERE id=?", (request.form.get("id", type=int),), one=True)
            role = request.form.get("role")
            if not target or target["id"] == me["id"] or target["role"] not in assignable or role not in assignable:
                abort(403)
            run("UPDATE users SET role=?, active=? WHERE id=?", (role, 1 if request.form.get("active") else 0, target["id"]))
            flash(f"Updated {target['name']}.", "ok")
            return redirect(url_for("admin.users"))
        vals, errs = validate(fields, request.form)
        if not errs:
            vals["email"] = vals["email"].lower()
            if pw_error(vals["password"]):
                errs["password"] = pw_error(vals["password"])
            elif q("SELECT 1 FROM users WHERE email=?", (vals["email"],), one=True):
                errs["email"] = "An account with this email already exists."
        if not errs:
            uid = run("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                      (vals["name"], vals["email"], generate_password_hash(vals["password"]), vals["role"]))
            if vals["role"] == "patient":
                run("INSERT INTO patients(user_id,name) VALUES(?,?)", (uid, vals["name"]))
            flash("User created.", "ok")
            return redirect(url_for("admin.users"))
        vals.pop("password", None)
    rows = q("SELECT id,name,email,role,active,substr(created,1,10) AS joined FROM users ORDER BY id")
    return render_template("users.html", rows=rows, fields=prep(fields), vals=vals, errs=errs, roles=assignable, assignable=assignable)


def _last_months(count=6):
    """The last `count` months as (YYYY-MM, short label), oldest first."""
    today, out = date.today(), []
    for back in range(count - 1, -1, -1):
        month, year = today.month - back, today.year
        while month <= 0:
            month, year = month + 12, year - 1
        out.append((f"{year}-{month:02d}", calendar.month_abbr[month]))
    return out


@bp.route("/reports")
@login_required(*ADMINS)
def reports():
    today = date.today().isoformat()
    total_appts = n("SELECT COUNT(*) FROM appointments")
    cancelled = n("SELECT COUNT(*) FROM appointments WHERE status='Cancelled'")
    tiles = [("Patients", n("SELECT COUNT(*) FROM patients")), ("Doctors", n("SELECT COUNT(*) FROM doctors")),
             ("Appointments", total_appts), ("Today", n("SELECT COUNT(*) FROM appointments WHERE date=?", (today,))),
             ("Cancelled", f"{round(100 * cancelled / total_appts)}%" if total_appts else "0%"),
             ("Average rating", str(n("SELECT ROUND(AVG(rating),1) FROM feedback") or "n/a"))]
    occupancy = n("SELECT COALESCE(SUM(occupied),0)*100.0/NULLIF(SUM(total),0) FROM beds")

    months = _last_months()
    per_month = dict(q("SELECT substr(date,1,7), COUNT(*) FROM appointments WHERE date>=? GROUP BY 1", (months[0][0] + "-01",)))
    status_order = {"Completed": 0, "Confirmed": 1, "Pending": 2, "Cancelled": 3}   # blue, green, amber, red
    statuses = sorted(q("SELECT status, COUNT(*) FROM appointments GROUP BY status"), key=lambda r: status_order.get(r[0], 9))
    ratings = dict(q("SELECT rating, COUNT(*) FROM feedback GROUP BY rating"))
    queue_rows = q("SELECT d.specialty, COALESCE(SUM(e.status='Done'),0), COALESCE(SUM(e.status='In consultation'),0), COALESCE(SUM(e.status='Waiting'),0) "
                   "FROM queue_entries e JOIN doctors d ON d.id=e.doctor_id WHERE e.day=? GROUP BY d.specialty ORDER BY d.specialty", (today,))
    dept_rows = [tuple(r) for r in q("SELECT d.specialty, COUNT(a.id) AS c FROM doctors d LEFT JOIN appointments a ON a.doctor_id=d.id "
                                     "GROUP BY d.specialty ORDER BY c DESC, d.specialty")]
    charts = dict(
        monthly=charts_lib.columns([(label, per_month.get(key, 0)) for key, label in months], "Appointments per month", w=980, h=250),
        status=charts_lib.donut([(r[0], r[1]) for r in statuses], "Appointments by status", {k: v for k, v in status_order.items()}),
        department=charts_lib.hbar(dept_rows, "Appointments by department", colors=[charts_lib.pastel(DEPT_COLORS.get(r[0], "#3b82c4"), 0.5) for r in dept_rows]),
        doctors=charts_lib.hbar([tuple(r) for r in q("SELECT d.name, COUNT(a.id) AS c FROM doctors d LEFT JOIN appointments a ON a.doctor_id=d.id "
                                                     "GROUP BY d.id ORDER BY c DESC, d.name LIMIT 8")], "Appointments per doctor"),
        wards=charts_lib.progress([tuple(r) for r in q("SELECT ward, occupied, total FROM beds ORDER BY ward")], "Ward occupancy"),
        queue=charts_lib.stacked([(r[0], [r[1], r[2], r[3]]) for r in queue_rows], [("Seen", "c1"), ("In consultation", "c0"), ("Waiting", "c2")], "Today's queue by department"),
        ratings=charts_lib.columns([(f"{star} star" if star == 1 else f"{star} stars", ratings.get(star, 0)) for star in range(1, 6)], "Patient ratings", classes=["c3", "c3", "c2", "c1", "c1"]),
        roles=charts_lib.donut([tuple(r) for r in q("SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role")], "Users by role"),
    )
    low = q("SELECT item,qty,unit,reorder_level FROM inventory WHERE qty<=reorder_level ORDER BY qty")
    return render_template("reports.html", tiles=tiles, occupancy=round(occupancy or 0), charts=charts, low=low)


@bp.post("/users/view-as")
@login_required("superadmin")
def view_as():
    """Super admin only: see the app exactly as another user sees it."""
    me = current_user()
    target = q("SELECT * FROM users WHERE id=? AND active=1", (request.form.get("id", type=int),), one=True)
    if not target or target["role"] == "superadmin" or target["id"] == me["id"]:
        abort(403)
    session["impersonator"], session["uid"] = me["id"], target["id"]
    flash(f"You are now viewing HealthSync as {target['name']} ({target['role']}).", "info")
    return redirect(url_for("dashboard.index"))


@bp.post("/users/stop-view")
def stop_view():
    real = session.pop("impersonator", None)
    boss = q("SELECT id FROM users WHERE id=? AND role='superadmin' AND active=1", (real,), one=True) if real else None
    if not boss:
        session.clear()
        return redirect(url_for("auth.login"))
    session["uid"] = boss["id"]
    flash("Back to your super admin account.", "ok")
    return redirect(url_for("admin.users"))
