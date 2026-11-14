from datetime import date
from flask import Blueprint, render_template
from .. import claims_client
from ..claims_client import ClaimsError
from ..constants import DESKS
from ..db import n, q
from ..security import current_user, login_required
from ..services import my_doctor, my_patient

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required()
def index():
    user = current_user()
    role, today = user["role"], date.today().isoformat()
    live = "a.status IN ('Pending','Confirmed')"
    beds_tile = ("Beds free now", n("SELECT COALESCE(SUM(total-occupied),0) FROM beds"), "records.beds")
    low_tile = ("Low-stock items", n("SELECT COUNT(*) FROM inventory WHERE qty<=reorder_level"), "records.inventory")
    users_tile = ("Registered users", n("SELECT COUNT(*) FROM users"), "admin.users")
    scope = ""
    if role == "patient":
        scope = f"a.patient_id={int(my_patient(user))} AND "
        stats = [("Upcoming appointments", n(f"SELECT COUNT(*) FROM appointments a WHERE {scope}a.date>=? AND {live}", (today,)), "appointments.index"),
                 ("Completed visits", n(f"SELECT COUNT(*) FROM appointments a WHERE {scope}a.status='Completed'"), "appointments.index"), beds_tile]
        links = [("Book an appointment", "appointments.index"), ("My coverage", "claims.coverage"), ("My treatments", "claims.treatments"),
                 ("Hospital services", "public.services"), ("Send feedback", "feedback.index")]
    elif role in DESKS:
        def waiting(path, status):
            try:
                return len(claims_client.ours(claims_client.call("GET", path, user, params={"status": status})))
            except ClaimsError:
                return "n/a"
        stats = [("Pre-authorizations to decide", waiting("/desk/preauths", "SUBMITTED"), "claims.desk_preauths"),
                 ("Queries waiting for the hospital", waiting("/desk/preauths", "QUERY"), "claims.desk_preauths"),
                 ("Claims to decide", waiting("/desk/claims", "SUBMITTED"), "claims.desk_claims")]
        links = [("Review pre-authorizations", "claims.desk_preauths"), ("Review claims", "claims.desk_claims")]
    elif role == "admin":
        stats = [("Pending requests", n("SELECT COUNT(*) FROM appointments WHERE status='Pending'"), "appointments.index"),
                 ("Doctors", n("SELECT COUNT(*) FROM doctors"), "records.doctors"), users_tile, low_tile, beds_tile]
        links = [("Confirm appointments", "appointments.index"), ("Add a doctor", "records.doctors"), ("Update inventory", "records.inventory"),
                 ("View reports", "admin.reports"), ("Manage users", "admin.users")]
    else:   # doctor or super admin
        doctor = my_doctor(user)
        scope = f"a.doctor_id={int(doctor['id'])} AND " if doctor else ""
        qscope = f"e.doctor_id={int(doctor['id'])} AND " if doctor else ""
        stats = [("Appointments today", n(f"SELECT COUNT(*) FROM appointments a WHERE {scope}a.date=?", (today,)), "appointments.index"),
                 ("Pending requests", n(f"SELECT COUNT(*) FROM appointments a WHERE {scope}a.status='Pending'"), "appointments.index"),
                 ("Waiting in queue", n(f"SELECT COUNT(*) FROM queue_entries e WHERE {qscope}e.day=? AND e.status='Waiting'", (today,)), "queue.index"), beds_tile]
        links = [("Run my queue", "queue.index"), ("Manage appointments", "appointments.index")] + ([("Treatment cases", "claims.cases")] if role == "doctor" else [])
        if role == "superadmin":
            stats += [("Patients on file", n("SELECT COUNT(*) FROM patients"), "records.patients"), low_tile, users_tile]
            links = [("Manage appointments", "appointments.index"), ("Queue console", "queue.index"), ("Add a doctor", "records.doctors"),
                     ("Patient records", "records.patients"), ("Update inventory", "records.inventory"),
                     ("View reports", "admin.reports"), ("Manage users", "admin.users")]
    show_appts = role not in DESKS
    rows = q(f"SELECT a.date,a.time,p.name AS patient,d.name AS doctor,a.status FROM appointments a JOIN patients p ON p.id=a.patient_id "
             f"JOIN doctors d ON d.id=a.doctor_id WHERE {scope}a.date>=? AND {live} ORDER BY a.date,a.time LIMIT 8", (today,)) if show_appts else []
    return render_template("dashboard.html", stats=stats, rows=rows, links=links, show_appts=show_appts)
