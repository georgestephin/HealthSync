from datetime import date

TODAY = date.today().isoformat()


def ids(app):
    """Seeded: Rahul's confirmed appointment today, and the entry currently in consultation."""
    from healthsync.db import q
    with app.app_context():
        appt = q("SELECT id FROM appointments WHERE patient_id=1 AND date=? AND status='Confirmed'", (TODAY,), one=True)["id"]
        serving = q("SELECT id FROM queue_entries WHERE status='In consultation'", one=True)["id"]
        pending = q("SELECT id FROM appointments WHERE status='Pending' LIMIT 1", one=True)["id"]
    return str(appt), str(serving), str(pending)


def test_board_needs_login_and_hides_names(web, accounts):
    web().get("/queue/board", 302)
    accounts["admin"].get("/queue/board", 403)
    for role in ("patient", "doctor", "superadmin"):
        page = accounts[role].get("/queue/board")
        assert "Now serving" in page and "Sunita" not in page and ">Live queue<" in page


def test_patient_checks_in_and_sees_position(accounts, app):
    appt, _, pending = ids(app)
    p = accounts["patient"]
    assert "Check in" in p.get("/queue")
    assert "checked in" in p.text("/queue/checkin", appointment_id=appt)
    page = p.get("/queue")
    assert "1</b><span>person ahead of you" in page and "Your token" in page and "03" in page
    assert "already in a queue" in p.text("/queue/checkin", appointment_id=appt)
    assert p.post("/queue/checkin", follow=False, appointment_id=pending).status_code == 403  # someone else's appointment


def test_queue_runs_in_order_and_completes_appointment(accounts, app):
    appt, serving, _ = ids(app)
    p, d = accounts["patient"], accounts["doctor"]
    p.text("/queue/checkin", appointment_id=appt)
    assert "Call next patient" in d.get("/queue")
    assert "Finish the current" in d.text("/queue/action", action="call", doctor_id="1")
    d.text("/queue/action", action="complete", id=serving)
    assert "Token 03 called in" in d.text("/queue/action", action="call", doctor_id="1")
    assert "your turn" in p.get("/queue")
    from healthsync.db import q
    with app.app_context():
        entry = q("SELECT id FROM queue_entries WHERE patient_id=1 AND status='In consultation'", one=True)["id"]
    d.text("/queue/action", action="complete", id=str(entry))
    with app.app_context():
        assert q("SELECT status FROM appointments WHERE id=?", (appt,), one=True)["status"] == "Completed"


def test_queue_permissions(accounts, app):
    appt, serving, _ = ids(app)
    p, d, a = accounts["patient"], accounts["doctor"], accounts["superadmin"]
    assert accounts["admin"].post("/queue/walkin", follow=False, doctor_id="4", patient_id="8").status_code == 403
    accounts["admin"].get("/queue", 403)
    assert d.post("/queue/walkin", follow=False, doctor_id="1", patient_id="8").status_code == 403   # doctors cannot add walk-ins
    assert "Add a walk-in" not in d.get("/queue") and "Add a walk-in" in a.get("/queue")
    assert p.post("/queue/action", follow=False, action="call", doctor_id="1").status_code == 403
    assert p.post("/queue/action", follow=False, action="complete", id=serving).status_code == 403
    assert d.post("/queue/action", follow=False, action="call", doctor_id="4").status_code == 403  # another doctor's queue
    assert "Walk-in added" in a.text("/queue/walkin", doctor_id="4", patient_id="8")  # Divya has no active queue entry
    assert "Queue console" in a.get("/queue?doctor=4")


def test_leave_queue(accounts, app):
    appt, _, _ = ids(app)
    p = accounts["patient"]
    p.text("/queue/checkin", appointment_id=appt)
    from healthsync.db import q
    with app.app_context():
        entry = q("SELECT id FROM queue_entries WHERE patient_id=1 AND status='Waiting'", one=True)["id"]
    assert "left the queue" in p.text("/queue/action", action="leave", id=str(entry))
