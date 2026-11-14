from flask import Blueprint, abort, render_template
from ..constants import DEPT_INFO, SERVICES
from ..db import n, q

bp = Blueprint("public", __name__)


def slugify(name):
    return name.lower().replace(" ", "-")


def _departments():
    """Departments that have doctors, with a link slug and the doctors' names."""
    rows = q("SELECT specialty, COUNT(*) AS n, GROUP_CONCAT(name, ', ') AS names FROM (SELECT * FROM doctors ORDER BY name) GROUP BY specialty ORDER BY specialty")
    return [dict(specialty=r["specialty"], n=r["n"], names=r["names"], slug=slugify(r["specialty"]), info=DEPT_INFO.get(r["specialty"], "")) for r in rows]


@bp.route("/")
def index():
    return render_template(
        "index.html",
        beds=q("SELECT * FROM beds ORDER BY ward"),
        free_beds=n("SELECT COALESCE(SUM(total-occupied),0) FROM beds"),
        departments=_departments(),
        doctors=q("SELECT * FROM doctors WHERE id IN (SELECT MIN(id) FROM doctors GROUP BY specialty) ORDER BY specialty"),
        reviews=q("SELECT f.rating, f.message, u.name, substr(f.created,1,10) AS day FROM feedback f "
                  "LEFT JOIN users u ON u.id=f.user_id WHERE f.rating>=4 ORDER BY f.id DESC LIMIT 3"))


@bp.route("/services")
def services():
    groups = {}
    for d in q("SELECT * FROM doctors ORDER BY specialty, name"):
        groups.setdefault(d["specialty"], []).append(d)
    return render_template("services.html", services=SERVICES, groups=groups)


@bp.route("/departments/<slug>")
def department(slug):
    """Public page: one department's doctors with their available days and fees."""
    doctors = [d for d in q("SELECT * FROM doctors ORDER BY name") if slugify(d["specialty"]) == slug]
    if not doctors:
        abort(404)
    name = doctors[0]["specialty"]
    return render_template("department.html", dept=name, info=DEPT_INFO.get(name, ""), doctors=doctors, others=_departments())
