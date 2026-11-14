from collections import Counter


def test_every_department_has_two_doctors_including_surgeries(app):
    from healthsync.db import q
    with app.app_context():
        counts = Counter(r["specialty"] for r in q("SELECT specialty FROM doctors"))
    assert {"General Surgery", "Cardiothoracic Surgery"} <= set(counts)
    assert len(counts) == 5 and all(n == 2 for n in counts.values()), counts


def test_ten_patients_have_logins_and_appointments(app):
    from healthsync.db import q
    with app.app_context():
        patients = q("SELECT id, user_id FROM patients")
        assert len(patients) >= 6 and all(p["user_id"] for p in patients)
        with_appt = {r["patient_id"] for r in q("SELECT DISTINCT patient_id FROM appointments")}
        assert {p["id"] for p in patients} <= with_appt


def test_every_demo_account_can_log_in(app, web):
    from healthsync.demo_data import demo_groups
    rows = [r for g in demo_groups() for r in g["rows"]]
    assert len(rows) == 24   # 10 patients, 10 doctors, 2 insurance desks, 1 admin, 1 super admin
    for r in rows:
        assert web(r["email"], r["password"]).get("/dashboard"), r["email"]


def test_login_page_lists_grouped_demo_accounts(web):
    from healthsync.demo_data import demo_groups
    page = web().get("/login")
    for title in ("Patients", "Doctors", "Insurance desks", "Admin and super admin", "General Surgery", "Cardiothoracic Surgery"):
        assert title in page
    for g in demo_groups():
        for r in g["rows"]:
            assert r["email"] in page and r["password"] in page
    assert "Click any row to fill the form above" not in page and "Sample logins created on first run" not in page


def test_queues_are_live_in_every_department(app):
    from healthsync.db import q
    from healthsync.queue_logic import doctor_queue
    busy = set()
    with app.app_context():
        for d in q("SELECT id, specialty FROM doctors"):
            state = doctor_queue(d["id"])
            if state["serving"] or state["waiting"]:
                busy.add(d["specialty"])
    assert len(busy) == 5, busy


def test_board_shows_a_queue_for_many_doctors(accounts):
    page = accounts["superadmin"].get("/queue/board")
    assert page.count("Now serving") >= 10 and page.count("waiting") >= 2


def test_reports_have_charts(accounts):
    page = accounts["admin"].get("/reports")
    assert page.count('<svg class="chart') >= 7
    for title in ("Appointments per month", "Appointments by status", "Appointments by department", "Ward occupancy", "Patient ratings"):
        assert title in page
    assert "General Surgery" in page and "Cardiothoracic Surgery" in page and "Surgical Ward" in page and "Ward occupancy" in page


def test_reports_work_on_an_empty_database(tmp_path):
    from healthsync import create_app
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "empty.db"), "SEED_DEMO_DATA": False})
    assert "No data yet" in _empty_reports(app)


def _empty_reports(app):
    from tests.conftest import Web
    runner = app.test_cli_runner()
    runner.invoke(args=["create-user", "boss@x.com", "Boss", "--role", "superadmin"], input="Str0ngpass\nStr0ngpass\n")
    return Web(app, "boss@x.com", "Str0ngpass").get("/reports")


def test_departments_are_public_clickable_and_show_doctors(web, accounts, app):
    from healthsync.db import q
    anon = web()
    home = anon.get("/")
    with app.app_context():
        specialties = sorted({r["specialty"] for r in q("SELECT specialty FROM doctors")})
    assert len(specialties) == 5
    for name in specialties:
        slug = name.lower().replace(" ", "-")
        assert f'href="/departments/{slug}"' in home
        page = anon.get(f"/departments/{slug}")
        assert page.count("data-doctor=") == 2 and name in page
        assert "Available days" in page and "Consultation fee" in page and "₹" in page
        assert "@healthsync.local" not in page          # no logins or contact details are shown publicly
    cardiology = anon.get("/departments/cardiology")
    assert "Dr. Anita Sharma" in cardiology and "Dr. Rohan Mehta" in cardiology and "Mon, Wed, Fri" in cardiology and "₹800" in cardiology
    assert "Dr. Anita Sharma" in home                                      # still listed under "Our doctors"
    assert "View doctors, availability and fees" not in home and "Choose a department to see" not in home
    from healthsync.constants import DEPT_INFO
    for name in specialties:
        assert DEPT_INFO[name] in home                                     # each tile carries a short description
    anon.get("/departments/not-a-department", 404)
    assert "Book a visit" in anon.get("/departments/cardiology") and "Book a visit" in accounts["patient"].get("/departments/cardiology")
    assert "Book a visit" not in accounts["doctor"].get("/departments/cardiology")


def _hex_colours(text):
    import re
    return set(re.findall(r"#[0-9a-fA-F]{6}\b", text))


def test_theme_has_no_purple_hues(app):
    import colorsys, pathlib
    from healthsync.constants import DEPT_COLORS
    css = pathlib.Path("healthsync/static/style.css").read_text()
    for colour in _hex_colours(css) | set(DEPT_COLORS.values()):
        r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        hue, _light, sat = colorsys.rgb_to_hls(r, g, b)
        assert not (250 <= hue * 360 <= 325 and sat > 0.12), f"{colour} is a purple hue"


def test_chart_colours_are_pastel(accounts):
    import colorsys, pathlib, re
    css = pathlib.Path("healthsync/static/style.css").read_text()
    chart_colours = re.findall(r"\.c\d\{--c:(#[0-9a-fA-F]{6})\}", css)
    assert len(chart_colours) == 6
    for colour in chart_colours:
        r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        assert colorsys.rgb_to_hls(r, g, b)[1] >= 0.7, f"{colour} is not a soft pastel"
    page = accounts["admin"].get("/reports")
    # department bars are lightened versions of the department colours
    from healthsync.charts import pastel
    from healthsync.constants import DEPT_COLORS
    assert pastel(DEPT_COLORS["Cardiology"]) in page and "#c0505e" not in page
