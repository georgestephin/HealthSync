from datetime import date, datetime
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from ..constants import CARE, SUPERADMIN
from ..db import n, q
from ..live import page as _page
from ..queue_logic import add_entry, board_rows, call_next, doctor_queue, finish, leave, my_entries
from ..security import current_user, login_required
from ..services import my_doctor, my_patient

bp = Blueprint("queue", __name__, url_prefix="/queue")


def can_manage(user, doctor_id):
    if user["role"] == "superadmin":
        return True
    if user["role"] == "doctor":
        mine = my_doctor(user)
        return mine is None or mine["id"] == doctor_id
    return False


def _back(doctor_id=None):
    return redirect(url_for("queue.index", doctor=doctor_id))


@bp.route("/", strict_slashes=False)
@login_required("patient", *CARE)
def index():
    user, today = current_user(), date.today().isoformat()
    if user["role"] == "patient":
        pid = my_patient(user)
        entries, history = my_entries(pid)
        appts = []
        for a in q("SELECT a.id,a.time,a.status,d.name AS doctor FROM appointments a JOIN doctors d ON d.id=a.doctor_id "
                   "WHERE a.patient_id=? AND a.date=? ORDER BY a.time", (pid, today)):
            a = dict(a)
            used = q("SELECT 1 FROM queue_entries WHERE appointment_id=?", (a["id"],), one=True)
            a["can_checkin"] = a["status"] == "Confirmed" and not used
            a["note"] = "Already checked in" if used else ("Waiting for the clinic to confirm" if a["status"] == "Pending" else "" if a["status"] == "Confirmed" else a["status"])
            appts.append(a)
        return _page("queue.html", fragment="_queue_live.html", mode="patient", entries=entries, history=history, appts=appts, sel=None)
    doctors = q("SELECT id,name,specialty FROM doctors ORDER BY name")
    mine = my_doctor(user)
    chosen = request.args.get("doctor", type=int)
    sel = mine["id"] if mine else (chosen or (doctors[0]["id"] if doctors else None))
    doctor = next((d for d in doctors if d["id"] == sel), None)
    state = doctor_queue(sel) if doctor else None
    stats = dict(done=n("SELECT COUNT(*) FROM queue_entries WHERE doctor_id=? AND day=? AND status='Done'", (sel, today)),
                 noshow=n("SELECT COUNT(*) FROM queue_entries WHERE doctor_id=? AND day=? AND status='No-show'", (sel, today))) if doctor else None
    return _page("queue.html", fragment="_queue_live.html", mode="staff", doctors=doctors, doctor=doctor, sel=sel, locked=bool(mine),
                 state=state, stats=stats, patients=q("SELECT id,name FROM patients ORDER BY name") if user["role"] == "superadmin" else [])


@bp.route("/board")
@login_required("patient", *CARE)
def board():
    return _page("board.html", fragment="_queue_board.html", board=board_rows())


@bp.post("/checkin")
@login_required("patient", *CARE)
def checkin():
    user = current_user()
    appt = q("SELECT * FROM appointments WHERE id=?", (request.form.get("appointment_id", type=int),), one=True) or abort(404)
    if not (user["role"] in CARE or appt["patient_id"] == my_patient(user)):
        abort(403)
    if appt["date"] != date.today().isoformat() or appt["status"] != "Confirmed":
        flash("You can only check in to a confirmed appointment on the day of the visit.", "error")
        return _back(appt["doctor_id"] if user["role"] != "patient" else None)
    token, err = add_entry(appt["patient_id"], appt["doctor_id"], appt["id"])
    flash(f"You are checked in. Your token is {token:02d}." if token else err, "ok" if token else "error")
    return _back(appt["doctor_id"] if user["role"] != "patient" else None)


@bp.post("/walkin")
@login_required(*SUPERADMIN)
def walkin():
    user, did, pid = current_user(), request.form.get("doctor_id", type=int), request.form.get("patient_id", type=int)
    if not (did and pid and q("SELECT 1 FROM patients WHERE id=?", (pid,), one=True) and can_manage(user, did)):
        abort(403)
    token, err = add_entry(pid, did)
    flash(f"Walk-in added with token {token:02d}." if token else err, "ok" if token else "error")
    return _back(did)


@bp.post("/action")
@login_required("patient", *CARE)
def action():
    user, act = current_user(), request.form.get("action")
    eid, did = request.form.get("id", type=int), request.form.get("doctor_id", type=int)
    if act == "call":
        if user["role"] not in CARE or not did or not can_manage(user, did):
            abort(403)
        token, err = call_next(did)
        flash(f"Token {token:02d} called in." if token else err, "ok" if token else "error")
        return _back(did)
    entry = q("SELECT * FROM queue_entries WHERE id=?", (eid,), one=True) or abort(404)
    staff_ok = user["role"] in CARE and can_manage(user, entry["doctor_id"])
    if act == "leave" and (staff_ok or entry["patient_id"] == my_patient(user)):
        ok = leave(eid, "Left")
        flash("You have left the queue." if ok else "That entry can no longer be changed.", "info" if ok else "error")
    elif act in ("complete", "noshow") and staff_ok:
        ok = finish(eid) if act == "complete" else leave(eid, "No-show")
        flash("Saved." if ok else "That entry can no longer be changed.", "ok" if ok else "error")
    else:
        abort(403)
    return _back(entry["doctor_id"] if user["role"] in CARE else None)
