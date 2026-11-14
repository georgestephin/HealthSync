from datetime import date, timedelta
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from ..constants import HMS_ROLES, SLOTS, STAFF
from ..db import q, run
from ..security import current_user, login_required
from ..services import my_doctor, my_patient
from ..validation import prep, validate

bp = Blueprint("appointments", __name__)

INTRO = {"patient": "Book a visit and follow it from request to completion.",
         "admin": "Review new patient requests and confirm visits. Only admins can confirm an appointment.",
         "doctor": "Follow your schedule and complete visits once the patient has been seen. Admins confirm new requests.",
         "superadmin": "Follow every appointment. Admins confirm new requests and doctors complete visits."}


def booking_fields(staff, today, last_day):
    fields = [dict(name="doctor_id", label="Doctor", type="select",
                   options=lambda: [(d["id"], f'{d["name"]} ({d["specialty"]})') for d in q("SELECT * FROM doctors ORDER BY name")]),
              dict(name="date", label="Date", type="date", min=today.isoformat(), max=last_day.isoformat()),
              dict(name="time", label="Time slot", type="select", options=SLOTS),
              dict(name="reason", label="Reason for visit", type="textarea", required=False)]
    return fields


def change_status(user, patient_id, doctor):
    """Handle the Confirm / Complete / Cancel buttons.
    Confirm: admin only. Complete: the appointment's doctor or the super admin. Cancel: the patient, the admin, the super admin or the doctor."""
    role, action = user["role"], request.form.get("_action")
    appt = q("SELECT * FROM appointments WHERE id=?", (request.form.get("id", type=int),), one=True) or abort(404)
    own_doctor = role == "doctor" and (not doctor or appt["doctor_id"] == doctor["id"])
    live = appt["status"] in ("Pending", "Confirmed")
    if action == "Confirmed" and role == "admin" and appt["status"] == "Pending":
        new = "Confirmed"
    elif action == "Completed" and (own_doctor or role == "superadmin") and appt["status"] == "Confirmed":
        new = "Completed"
    elif action == "cancel" and live and (appt["patient_id"] == patient_id or role in ("admin", "superadmin") or own_doctor):
        new = "Cancelled"
    else:
        abort(403)
    run("UPDATE appointments SET status=? WHERE id=?", (new, appt["id"]))
    flash(f"Appointment {new.lower()}.", "ok")
    return redirect(url_for("appointments.index"))


@bp.route("/appointments", methods=["GET", "POST"])
@login_required(*HMS_ROLES)
def index():
    user = current_user()
    role, staff = user["role"], user["role"] in STAFF
    patient_id, doctor = my_patient(user), my_doctor(user)
    today = date.today()
    last_day = today + timedelta(days=current_app.config["BOOKING_WINDOW_DAYS"])
    fields = booking_fields(staff, today, last_day)
    vals, errs = {}, {}

    if request.method == "POST":
        if request.form.get("_action"):
            return change_status(user, patient_id, doctor)
        if staff:
            abort(403)  # only patients book their own appointments
        vals, errs = validate(fields, request.form)
        vals["patient_id"] = patient_id
        if not errs:
            day = date.fromisoformat(vals["date"])
            if not today <= day <= last_day:
                errs["date"] = f"Choose a date within the next {current_app.config['BOOKING_WINDOW_DAYS']} days."
            elif q("SELECT 1 FROM appointments WHERE doctor_id=? AND date=? AND time=? AND status!='Cancelled'",
                   (vals["doctor_id"], vals["date"], vals["time"]), one=True):
                errs["time"] = "That slot is already booked. Pick another time."
        if not errs:
            run("INSERT INTO appointments(patient_id,doctor_id,date,time,reason) VALUES(?,?,?,?,?)",
                (vals["patient_id"], vals["doctor_id"], vals["date"], vals["time"], vals["reason"]))
            flash("Appointment requested. Track its status in the list below.", "ok")
            return redirect(url_for("appointments.index"))

    sql = ("SELECT a.id,a.date,a.time,a.reason,a.status,p.name AS patient,d.name AS doctor FROM appointments a "
           "JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id")
    where, args = "", ()
    if role == "patient":
        where, args = " WHERE a.patient_id=?", (patient_id,)
    elif doctor:
        where, args = " WHERE a.doctor_id=?", (doctor["id"],)
    rows = [dict(r) for r in q(sql + where + " ORDER BY a.date DESC, a.time", args)]
    for r in rows:
        r["acts"] = []
        if role == "admin" and r["status"] == "Pending":
            r["acts"].append(dict(label="Confirm", action="Confirmed", kind="primary"))
        if role in ("doctor", "superadmin") and r["status"] == "Confirmed":
            r["acts"].append(dict(label="Complete", action="Completed", kind="primary"))
        if role == "doctor" and r["status"] in ("Confirmed", "Completed"):
            r["acts"].append(dict(label="Recommend treatment", url=url_for("claims.recommend", appointment_id=r["id"])))
        if r["status"] in ("Pending", "Confirmed"):
            r["acts"].append(dict(label="Cancel", action="cancel", kind="danger", confirm="Cancel this appointment?"))
    page = dict(title="Appointments", show_form=not staff, form_title="Book an appointment", submit="Request appointment",
                intro=INTRO[role],
                fields=prep(fields), rows=rows, badges={"status"}, empty="No appointments to show yet." if staff else "No appointments yet. Use the form to book your first visit.",
                cols=[("Date", "date"), ("Time", "time")] + ([("Patient", "patient")] if staff else []) + [("Doctor", "doctor"), ("Reason", "reason"), ("Status", "status")])
    return render_template("crud.html", c=page, vals=vals, errs=errs, edit_id=None)
