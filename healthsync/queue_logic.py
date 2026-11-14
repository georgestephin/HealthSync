"""Live outpatient queue. First come, first served: tokens are numbered per doctor per day."""
import sqlite3
from datetime import date, datetime
from flask import current_app
from .db import get_db, q

ACTIVE = ("Waiting", "In consultation")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _minutes_since(stamp):
    return max((datetime.now() - datetime.fromisoformat(stamp)).total_seconds() / 60, 0)


def avg_minutes(doctor_id):
    """Average length of this doctor's recent consultations (ignores accidental sub-minute clicks)."""
    rows = q("SELECT started, finished FROM queue_entries WHERE doctor_id=? AND status='Done' AND started IS NOT NULL "
             "AND finished IS NOT NULL ORDER BY id DESC LIMIT 20", (doctor_id,))
    mins = [(datetime.fromisoformat(r["finished"]) - datetime.fromisoformat(r["started"])).total_seconds() / 60 for r in rows]
    mins = [m for m in mins if m >= 1]
    if not mins:
        return float(current_app.config["QUEUE_DEFAULT_MINUTES"])
    return min(max(sum(mins) / len(mins), 3.0), 45.0)


def doctor_queue(doctor_id):
    """Today's live state for one doctor: who is being seen, who is waiting, and estimated waits."""
    rows = q("SELECT e.*, p.name AS patient FROM queue_entries e JOIN patients p ON p.id=e.patient_id "
             "WHERE e.doctor_id=? AND e.day=? AND e.status IN ('Waiting','In consultation') ORDER BY e.token",
             (doctor_id, date.today().isoformat()))
    serving = next((dict(r) for r in rows if r["status"] == "In consultation"), None)
    waiting = [dict(r) for r in rows if r["status"] == "Waiting"]
    avg = avg_minutes(doctor_id)
    remaining = 0.0
    if serving:
        serving["minutes"] = int(_minutes_since(serving["started"]))
        remaining = max(avg - _minutes_since(serving["started"]), 1.0)
    for i, w in enumerate(waiting):
        w["ahead"] = i + (1 if serving else 0)
        w["est"] = int(round(remaining + i * avg))
        w["waited"] = int(_minutes_since(w["checked_in"]))
    return dict(serving=serving, waiting=waiting, avg=int(round(avg)), new_arrival_wait=int(round(remaining + len(waiting) * avg)))


def board_rows():
    """One row per doctor for the public board. Token numbers only, never names."""
    out = []
    for d in q("SELECT * FROM doctors ORDER BY specialty, name"):
        s = doctor_queue(d["id"])
        out.append(dict(d, serving_token=s["serving"]["token"] if s["serving"] else None,
                        waiting=len(s["waiting"]), est=s["new_arrival_wait"]))
    return out


def my_entries(patient_id):
    """A patient's queue entries today: (active, finished)."""
    rows = q("SELECT e.*, d.name AS doctor, d.specialty FROM queue_entries e JOIN doctors d ON d.id=e.doctor_id "
             "WHERE e.patient_id=? AND e.day=? ORDER BY e.id", (patient_id, date.today().isoformat()))
    active, history = [], []
    for r in rows:
        e = dict(r)
        if e["status"] in ACTIVE:
            state = doctor_queue(e["doctor_id"])
            e["serving_token"] = state["serving"]["token"] if state["serving"] else None
            mine = next((w for w in state["waiting"] if w["id"] == e["id"]), None)
            e["ahead"], e["est"] = (mine["ahead"], mine["est"]) if mine else (0, 0)
            active.append(e)
        else:
            history.append(e)
    return active, history


def add_entry(patient_id, doctor_id, appointment_id=None):
    """Join today's queue. Returns (token, error). Token assignment is one atomic SQL statement."""
    day = date.today().isoformat()
    if q("SELECT 1 FROM queue_entries WHERE patient_id=? AND day=? AND status IN ('Waiting','In consultation')", (patient_id, day), one=True):
        return None, "This patient is already in a queue today."
    sql = ("INSERT INTO queue_entries(patient_id,doctor_id,appointment_id,day,token,checked_in) VALUES(?,?,?,?,"
           "(SELECT COALESCE(MAX(token),0)+1 FROM queue_entries WHERE doctor_id=? AND day=?),?)")
    for _ in range(3):
        try:
            cur = get_db().execute(sql, (patient_id, doctor_id, appointment_id, day, doctor_id, day, _now()))
            get_db().commit()
            return q("SELECT token FROM queue_entries WHERE id=?", (cur.lastrowid,), one=True)["token"], None
        except sqlite3.IntegrityError:
            get_db().rollback()
    return None, "Could not join the queue. Please try again."


def _update(sql, args):
    cur = get_db().execute(sql, args)
    get_db().commit()
    return cur.rowcount


def call_next(doctor_id):
    day = date.today().isoformat()
    if q("SELECT 1 FROM queue_entries WHERE doctor_id=? AND day=? AND status='In consultation'", (doctor_id, day), one=True):
        return None, "Finish the current consultation first."
    nxt = q("SELECT id, token FROM queue_entries WHERE doctor_id=? AND day=? AND status='Waiting' ORDER BY token LIMIT 1", (doctor_id, day), one=True)
    if not nxt:
        return None, "No one is waiting."
    if _update("UPDATE queue_entries SET status='In consultation', started=? WHERE id=? AND status='Waiting'", (_now(), nxt["id"])):
        return nxt["token"], None
    return None, "Someone else just called the next patient."


def finish(entry_id):
    done = _update("UPDATE queue_entries SET status='Done', finished=? WHERE id=? AND status='In consultation'", (_now(), entry_id))
    if done:
        _update("UPDATE appointments SET status='Completed' WHERE id=(SELECT appointment_id FROM queue_entries WHERE id=?) AND status='Confirmed'", (entry_id,))
    return bool(done)


def leave(entry_id, status):
    """Remove a waiting entry as 'No-show' (staff) or 'Left' (the patient or staff)."""
    return bool(_update("UPDATE queue_entries SET status=?, finished=? WHERE id=? AND status='Waiting'", (status, _now(), entry_id)))
