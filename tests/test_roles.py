from datetime import date, timedelta

DAY = (date.today() + timedelta(days=6)).isoformat()


def user_id(app, email):
    from healthsync.db import q
    with app.app_context():
        return str(q("SELECT id FROM users WHERE email=?", (email,), one=True)["id"])


def test_only_patients_can_book(accounts):
    for role in ("doctor", "admin", "superadmin"):
        assert "Request appointment" not in accounts[role].get("/appointments")
        assert accounts[role].post("/appointments", follow=False, doctor_id="1", date=DAY, time="10:00").status_code == 403
    assert "Request appointment" in accounts["patient"].get("/appointments")


def test_booking_links_hidden_for_staff(accounts, web):
    assert "Book an appointment" in web().get("/")
    assert "Book an appointment" in accounts["patient"].get("/")
    for role in ("doctor", "admin", "superadmin"):
        home = accounts[role].get("/")
        assert "Book an appointment" not in home and "Book a visit" not in home and "Open your dashboard" in home


def test_only_the_admin_confirms_appointments(accounts, app):
    from healthsync.db import q
    accounts["patient"].text("/appointments", doctor_id="1", date=DAY, time="12:00", reason="Check")
    with app.app_context():
        appt = str(q("SELECT MAX(id) AS m FROM appointments", one=True)["m"])
        assert q("SELECT status FROM appointments WHERE id=?", (appt,), one=True)["status"] == "Pending"
    for role in ("patient", "doctor", "superadmin"):
        assert accounts[role].post("/appointments", follow=False, _action="Confirmed", id=appt).status_code == 403, role
    assert ">Confirm</button>" not in accounts["doctor"].get("/appointments")
    assert ">Confirm</button>" in accounts["admin"].get("/appointments")
    assert "Appointment confirmed" in accounts["admin"].text("/appointments", _action="Confirmed", id=appt)
    assert accounts["admin"].post("/appointments", follow=False, _action="Completed", id=appt).status_code == 403   # admins confirm, they do not complete
    assert "Appointment completed" in accounts["doctor"].text("/appointments", _action="Completed", id=appt)


def test_each_dashboard_shows_only_that_roles_actions(accounts):
    doctor = accounts["doctor"].get("/dashboard")
    assert "Run my queue" in doctor and "Manage appointments" in doctor and "Beds free now" in doctor
    for gone in ("Patient records", "Update inventory", "Manage users", "Confirm appointments"):
        assert gone not in doctor
    admin = accounts["admin"].get("/dashboard")
    for present in ("Confirm appointments", "Add a doctor", "Update inventory", "View reports", "Manage users", "Pending requests", "Beds free now"):
        assert present in admin
    for gone in ("Queue console", "Patient records", "Manage appointments"):
        assert gone not in admin
    sup = accounts["superadmin"].get("/dashboard")
    for present in ("Manage appointments", "Queue console", "Patient records", "Manage users"):
        assert present in sup
    assert "Confirm appointments" not in sup


def test_portal_menus_by_role(accounts):
    menu = lambda role: accounts[role].get("/dashboard").split('aria-label="Portal"')[1].split("</nav>")[0]
    assert all(x in menu("patient") for x in ("/appointments", "/queue", "/feedback")) and "/patients" not in menu("patient")
    doctor = menu("doctor")
    assert "/appointments" in doctor and "/queue" in doctor and "/patients" not in doctor and "/inventory" not in doctor
    admin = menu("admin")
    assert all(x in admin for x in ("/appointments", "/inventory", "/reports", "/users", "/feedback"))
    assert all(x not in admin for x in ("/queue", "/patients"))
    sup = menu("superadmin")
    assert all(x in sup for x in ("/appointments", "/queue", "/patients", "/inventory", "/reports", "/users"))


def test_bed_availability_is_shown_and_occupancy_chart_stays(accounts, web):
    home = web().get("/")
    assert "Ward directory" in home and "Check bed availability" in home and "Open the full directory" in home
    beds = web().get("/beds")
    assert "Bed availability" in beds and "free of" in beds
    for role in ("patient", "doctor", "admin"):
        page = accounts[role].get("/dashboard")
        assert "Beds free now" in page and ">Bed availability<" in page
    reports = accounts["admin"].get("/reports")
    assert "Ward occupancy" in reports and "Update bed counts" in reports


def test_only_admins_add_doctors_in_one_step(accounts, app, web):
    assert accounts["doctor"].post("/doctors", follow=False, name="Dr. Sneak", specialty="ENT", fee="100").status_code == 403
    admin = accounts["admin"]
    assert "Login email" in admin.get("/doctors")
    bad = admin.text("/doctors", name="Dr. Joy Nurse", specialty="ENT", fee="300", login_email="joy@h.local", login_password="short")
    assert "at least 8 characters" in bad
    ok = admin.text("/doctors", name="Dr. Joy Nurse", specialty="ENT", fee="300", available_days="Mon", login_email="joy@h.local", login_password="Nurse123x")
    assert "Saved successfully" in ok and "Dr. Joy Nurse" in ok
    assert "already exists" in admin.text("/doctors", name="Dr. Other", specialty="ENT", fee="300", login_email="joy@h.local", login_password="Nurse123x")
    joy = web("joy@h.local", "Nurse123x")           # the new doctor can log in and sees only doctor tools
    joy.get("/queue"); joy.get("/patients", 403); joy.get("/users", 403)


def test_link_existing_login_when_editing(accounts, app):
    from healthsync.db import q
    admin = accounts["admin"]
    admin.text("/users", name="Nurse Ray", email="ray@h.local", password="Nurse123x", role="doctor")
    admin.text("/doctors", name="Dr. Ray", specialty="ENT", fee="200")
    with app.app_context():
        doc = str(q("SELECT id FROM doctors WHERE name='Dr. Ray'", one=True)["id"])
    uid = user_id(app, "ray@h.local")
    assert "Saved" in admin.text("/doctors", id=doc, name="Dr. Ray", specialty="ENT", fee="200", user_id=uid)
    assert "already linked" in admin.text("/doctors", id="1", name="Dr. Anita Sharma", specialty="Cardiology", fee="800", user_id=uid)


def test_super_admin_can_view_as_any_account(accounts, app, web):
    sup = accounts["superadmin"]
    for email, expect in [("patient@healthsync.local", "My queue"), ("sunita@healthsync.local", "My queue"),
                          ("vikram@healthsync.local", "Run my queue"), ("doctor@healthsync.local", "Waiting in queue")]:
        page = sup.text("/users/view-as", id=user_id(app, email))
        assert "You are viewing HealthSync as" in page and expect in page
        assert "Return to super admin" in sup.get("/dashboard")
        assert "Users and roles" in sup.text("/users/stop-view")           # back as super admin
        assert "You are viewing HealthSync as" not in sup.get("/users")


def test_view_as_is_super_admin_only_and_not_nestable(accounts, app):
    pid, sid = user_id(app, "patient@healthsync.local"), user_id(app, "superadmin@healthsync.local")
    assert accounts["admin"].post("/users/view-as", follow=False, id=pid).status_code == 403
    assert accounts["patient"].post("/users/view-as", follow=False, id=pid).status_code == 403
    sup = accounts["superadmin"]
    assert sup.post("/users/view-as", follow=False, id=sid).status_code == 403    # not another super admin / yourself
    sup.text("/users/view-as", id=pid)
    assert sup.post("/users/view-as", follow=False, id=user_id(app, "doctor@healthsync.local")).status_code == 403   # no nesting
    sup.get("/users", 403)                                                         # acts with the patient's permissions only
