from datetime import date, timedelta

DAY = (date.today() + timedelta(days=5)).isoformat()


def newest_appointment(app):
    from healthsync.db import q
    with app.app_context():
        return str(q("SELECT MAX(id) AS m FROM appointments", one=True)["m"])


def test_public_pages_and_protected_redirects(web):
    anon = web()
    for url in ["/", "/services", "/beds", "/doctors", "/login", "/register"]:
        anon.get(url)
    for url in ["/dashboard", "/patients", "/appointments", "/users", "/queue", "/queue/board"]:
        anon.get(url, 302)
    anon.get("/missing", 404)
    home = anon.get("/")
    assert "HealthSync" in home
    for gone in ("Outpatient queue", "multispecialty", "own colour"):
        assert gone not in home
    assert "HealthSync is a platform" in home and ">Live queue<" not in home
    assert "Ward directory" in home and "Bed availability" in home and "beds free" in home and "Open the full directory" in home


def test_register_validation_and_login(web):
    anon = web()
    assert "required" in anon.text("/register", name="A", email="bad", phone="123", age="200", gender="", password="short", confirm="x")
    ok = anon.text("/register", name="Neha Singh", email="neha@x.com", phone="9876543210", age="29", gender="Female",
                   password="Passw0rdz", confirm="Passw0rdz")
    assert "Account created" in ok
    assert "already exists" in anon.text("/register", name="Neha Singh", email="neha@x.com", phone="9876543210", age="29",
                                         gender="Female", password="Passw0rdz", confirm="Passw0rdz")
    neha = web("neha@x.com", "Passw0rdz")
    for url in ["/dashboard", "/appointments", "/feedback"]:
        neha.get(url)
    for url in ["/patients", "/inventory", "/reports", "/users"]:
        neha.get(url, 403)


def test_patient_booking_rules(accounts, app):
    p = accounts["patient"]
    assert "Appointment requested" in p.text("/appointments", doctor_id="1", date=DAY, time="10:00", reason="Checkup")
    assert "already booked" in p.text("/appointments", doctor_id="1", date=DAY, time="10:00")
    assert "within the next" in p.text("/appointments", doctor_id="1", date="2020-01-01", time="10:00")
    assert "Appointment cancelled" in p.text("/appointments", _action="cancel", id=newest_appointment(app))
    assert "Thank you" in p.text("/feedback", rating="5", message="Great service overall!")


def test_doctor_permissions(accounts, app):
    d, p = accounts["doctor"], accounts["patient"]
    p.text("/appointments", doctor_id="1", date=DAY, time="11:00", reason="Follow up")
    new = newest_appointment(app)
    assert d.post("/appointments", follow=False, _action="Confirmed", id=new).status_code == 403       # doctors cannot confirm
    assert "Appointment confirmed" in accounts["admin"].text("/appointments", _action="Confirmed", id=new)
    assert "Appointment completed" in d.text("/appointments", _action="Completed", id=new)             # the doctor completes the visit
    assert d.post("/appointments", follow=False, _action="Completed", id="2").status_code == 403       # another doctor's appointment
    for url in ["/patients", "/inventory", "/reports", "/users"]:
        d.get(url, 403)
    assert d.post("/patients", follow=False, _action="delete", id="1").status_code == 403


def test_admin_manages_inventory_and_beds_and_confirms_appointments(accounts):
    a = accounts["admin"]
    assert "Saved" in a.text("/inventory", item="Gauze", category="Supplies", qty="5", unit="rolls", reorder_level="10")
    assert "Low" in a.get("/inventory")
    assert "cannot exceed" in a.text("/beds", ward="X", total="5", occupied="9")
    assert "Saved" in a.text("/beds", ward="Day Care", total="10", occupied="4")
    page = a.get("/appointments")
    assert ">Confirm</button>" in page and "Request appointment" not in page
    for url in ["/patients", "/queue", "/queue/board"]:
        a.get(url, 403)


def test_super_admin_keeps_patient_records(accounts):
    s = accounts["superadmin"]
    assert "Saved successfully" in s.text("/patients", name="Test Patient", age="40", gender="Male", phone="9999999999")
    for url in ["/appointments", "/queue", "/inventory", "/beds", "/reports", "/users"]:
        s.get(url)
    assert ">Confirm</button>" not in s.get("/appointments")          # the super admin cannot confirm
    assert s.post("/appointments", follow=False, _action="Confirmed", id="2").status_code == 403


def test_csrf_is_enforced(accounts):
    d = accounts["doctor"]
    assert d.c.post("/patients", data={"name": "x"}).status_code == 400


def test_admin_user_management(accounts, web, app):
    from healthsync.db import q

    def uid(email):
        with app.app_context():
            return str(q("SELECT id FROM users WHERE email=?", (email,), one=True)["id"])
    admin, sup = accounts["admin"], accounts["superadmin"]
    for url in ["/reports", "/users", "/dashboard"]:
        admin.get(url)
    assert "User created" in admin.text("/users", name="Nurse Joy", email="joy@h.local", password="Nurse123x", role="doctor")
    assert admin.post("/users", follow=False, _action="update", id=uid("superadmin@healthsync.local"), role="patient", active="on").status_code == 403  # super admin is protected
    assert admin.post("/users", follow=False, _action="update", id=uid("patient@healthsync.local"), role="admin", active="on").status_code == 403  # admins cannot grant admin
    assert "Updated" in sup.text("/users", _action="update", id=uid("patient@healthsync.local"), role="admin", active="on")
    sup.text("/users", _action="update", id=uid("joy@h.local"), role="doctor")  # no "active" box -> disabled
    assert "disabled" in web().text("/login", email="joy@h.local", password="Nurse123x")
    sup.get("/reports")


def test_create_user_command(app):
    result = app.test_cli_runner().invoke(args=["create-user", "boss@x.com", "Boss", "--role", "superadmin"], input="Str0ngpass\nStr0ngpass\n")
    assert "Created superadmin" in result.output
    from tests.conftest import Web
    Web(app, "boss@x.com", "Str0ngpass").get("/users")
