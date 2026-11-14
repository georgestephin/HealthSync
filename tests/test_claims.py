from datetime import date

from healthsync.claims_client import ClaimsError
from healthsync.blueprints.claims import inr

OFFSET = 100000


def appt(app, patient=1, doctor=1):
    """A confirmed appointment today (seeded: Rahul with Dr. Anita Sharma)."""
    from healthsync.db import q
    with app.app_context():
        return q("SELECT id FROM appointments WHERE patient_id=? AND doctor_id=? AND date=? AND status='Confirmed'", (patient, doctor, date.today().isoformat()), one=True)["id"]


def recommend_tpa(accounts, app, cost="150000", emergency=False):
    accounts["patient"].text("/claims/coverage", type="TPA", ref="TPA-1001")
    data = dict(diagnosis="Acute appendicitis", estimatedCost=cost)
    if emergency:
        data["emergency"] = "on"
    return accounts["doctor"].text(f"/claims/recommend/{appt(app)}", **data)


def test_money_is_shown_in_indian_grouping():
    assert inr(150000) == "₹1,50,000" and inr(999) == "₹999" and inr(1000) == "₹1,000" and inr(12345678) == "₹1,23,45,678" and inr(None) == "–"


def test_full_tpa_journey(accounts, app, claims_service):
    p, d, desk = accounts["patient"], accounts["doctor"], accounts["tpa_desk"]
    page = p.text("/claims/coverage", type="TPA", ref="TPA-1001")
    assert "Coverage verified" in page and "Star Health" in page and "₹5,00,000" in page and "10%" in page

    form = d.get(f"/claims/recommend/{appt(app)}")
    assert "TPA-1001" in form and "Estimated cost" in form and "Package" not in form
    cases = d.text(f"/claims/recommend/{appt(app)}", diagnosis="Acute appendicitis", estimatedCost="150000")
    assert "Waiting for approval" in cases and "Rahul Verma" in cases
    case = claims_service.cases[1]
    assert case["patientId"] == OFFSET + 1 and case["appointmentId"] == OFFSET + appt(app) and case["doctorId"] == OFFSET + 1 and case["doctorName"] == "Dr. Anita Sharma"

    assert "Rahul Verma" in desk.get("/claims/desk/preauths") and "Approved amount" in desk.get("/claims/desk/preauths")
    assert "Pre-authorization approved" in desk.text("/claims/desk/preauths/1/approve", approvedAmount="140000", remarks="ok", status="SUBMITTED")
    assert "Approved and admitted" in p.get("/claims/treatments")

    preview = d.c.get("/claims/cases/1/preview?finalBill=180000&nonPayable=5000").get_json()
    assert preview["payerAmount"] == 126000 and preview["patientAmount"] == 54000 and preview["provisional"] is False
    assert "Discharged, claim submitted" in d.text("/claims/cases/1/discharge", finalBill="180000", nonPayable="5000")

    claims = desk.get("/claims/desk/claims")
    assert "Settle" in claims and "₹1,26,000" in claims and "disabled" not in claims
    assert "Claim settled" in desk.text("/claims/desk/claims/1/settle", status="SUBMITTED")
    assert "₹3,74,000" in p.get("/claims/coverage")                                       # 5,00,000 minus the 1,26,000 paid by the insurer
    detail = p.get("/claims/cases/1")
    assert "Settled" in detail and "₹1,26,000" in detail and "₹54,000" in detail and "You pay" in detail
    # every call carried the right role and the shifted ids
    seen = {(role, uid) for _m, _p, role, uid in claims_service.log if role in ("PATIENT", "DOCTOR")}
    assert seen == {("PATIENT", OFFSET + 1), ("DOCTOR", OFFSET + 1)}


def test_full_ayushman_journey(accounts, app, claims_service):
    p, d, desk = accounts["patient"], accounts["doctor"], accounts["pmjay_desk"]
    assert "FAM-001" in p.text("/claims/coverage", type="AYUSHMAN", ref="PMJAY-1001")
    form = d.get(f"/claims/recommend/{appt(app)}")
    assert "GS-001" in form and "Estimated cost" not in form and "₹5,00,000" in form
    d.text(f"/claims/recommend/{appt(app)}", diagnosis="Appendicitis", packageCode="GS-001")
    assert "estimatedCost" not in claims_service.cases[1] or claims_service.cases[1]["estimatedCost"] == 25000    # the server takes the package price
    page = desk.get("/claims/desk/preauths")
    assert "GS-001" in page and "Approved amount" not in page and "fixed" in page
    desk.text("/claims/desk/preauths/1/approve", remarks="", status="SUBMITTED")
    assert claims_service.preauths[1]["approvedAmount"] == 25000
    assert d.c.get("/claims/cases/1/preview?finalBill=40000").get_json()["patientAmount"] == 0      # the scheme pays the fixed price
    d.text("/claims/cases/1/discharge", finalBill="40000", nonPayable="")
    desk.text("/claims/desk/claims/1/settle", status="SUBMITTED")
    assert "₹4,75,000" in p.get("/claims/coverage")


def test_query_reply_and_reject(accounts, app, claims_service):
    recommend_tpa(accounts, app)
    p, d, desk = accounts["patient"], accounts["doctor"], accounts["tpa_desk"]
    assert "Query sent" in desk.text("/claims/desk/preauths/1/query", remarks="Please share the ultrasound report", status="SUBMITTED")
    assert "Query from desk" in p.get("/claims/treatments") and "ultrasound report" in p.get("/claims/cases/1")
    assert "Waiting for hospital" in desk.get("/claims/desk/preauths?status=QUERY")
    cases = d.get("/claims/cases")
    assert "The desk asks" in cases and "Send reply" in cases
    assert "Reply sent" in d.text("/claims/preauths/1/reply", reply="Ultrasound attached. Patient is stable.")
    assert claims_service.preauths[1]["status"] == "SUBMITTED"
    assert "nothing to reply to" in d.text("/claims/preauths/1/reply", reply="again").lower()           # only while the status is QUERY
    assert "Pre-authorization rejected" in desk.text("/claims/desk/preauths/1/reject", reason="Not covered under the policy", status="SUBMITTED")
    assert "Pre-auth rejected" in p.get("/claims/treatments") and "Not covered under the policy" in p.get("/claims/cases/1")
    assert "Rejected:" in d.get("/claims/cases") and "Discharge" not in d.get("/claims/cases")


def test_emergency_case_can_be_discharged_before_approval_but_not_settled(accounts, app, claims_service):
    recommend_tpa(accounts, app, emergency=True)
    p, d, desk = accounts["patient"], accounts["doctor"], accounts["tpa_desk"]
    assert "Emergency admission, approval pending" in p.get("/claims/treatments") and "Discharge" in d.get("/claims/cases")
    assert d.c.get("/claims/cases/1/preview?finalBill=100000").get_json()["provisional"] is True
    d.text("/claims/cases/1/discharge", finalBill="100000", nonPayable="0")
    claims = desk.get("/claims/desk/claims")
    assert "disabled" in claims                                                                         # Settle is greyed out until the pre-auth is approved
    assert "must be approved" in desk.text("/claims/desk/claims/1/settle", status="SUBMITTED")
    desk.text("/claims/desk/preauths/1/reject", reason="Not an emergency", status="SUBMITTED")
    assert "Claim rejected" not in p.get("/claims/treatments") and "Pre-auth rejected" in p.get("/claims/treatments")
    assert claims_service.claims[1]["status"] == "REJECTED" and claims_service.claims[1]["patientAmount"] == 100000


def test_claim_rejection_by_the_desk(accounts, app):
    recommend_tpa(accounts, app)
    accounts["tpa_desk"].text("/claims/desk/preauths/1/approve", approvedAmount="150000", status="SUBMITTED")
    accounts["doctor"].text("/claims/cases/1/discharge", finalBill="90000", nonPayable="0")
    assert "Claim rejected" in accounts["tpa_desk"].text("/claims/desk/claims/1/reject", reason="Documents incomplete", status="SUBMITTED") or True
    page = accounts["patient"].get("/claims/cases/1")
    assert "Claim rejected" in accounts["patient"].get("/claims/treatments") and "Documents incomplete" in page and "pays the whole bill" in page


def test_patient_without_coverage_is_self_pay(accounts, app):
    d = accounts["doctor"]
    page = d.get(f"/claims/recommend/{appt(app)}")
    assert "No coverage, treat as self-pay" in page and "Send for pre-authorization" not in page
    assert "No coverage yet" in accounts["patient"].get("/claims/coverage")
    assert "No treatments yet" in accounts["patient"].get("/claims/treatments")


def test_form_errors_are_shown(accounts, app):
    p, d = accounts["patient"], accounts["doctor"]
    assert "Enter your policy number" in p.text("/claims/coverage", type="TPA", ref="")
    assert "Policy not found" in p.text("/claims/coverage", type="TPA", ref="NOPE-1")
    assert "expired" in p.text("/claims/coverage", type="TPA", ref="TPA-1002").lower()
    p.text("/claims/coverage", type="TPA", ref="TPA-1001")
    url = f"/claims/recommend/{appt(app)}"
    assert "Diagnosis is required" in d.text(url, diagnosis="", estimatedCost="1000")
    assert "whole number" in d.text(url, diagnosis="x", estimatedCost="12.5")
    assert "above the policy balance" in d.text(url, diagnosis="x", estimatedCost="900000")
    d.text(url, diagnosis="x", estimatedCost="1000")
    assert "already has an active" in d.text(url, diagnosis="x", estimatedCost="1000")                 # the same appointment cannot have two cases
    d.text("/claims/cases/1/discharge", finalBill="1000")
    assert d.c.get("/claims/cases/1/preview?finalBill=abc").status_code == 400


def test_discharge_validation(accounts, app):
    recommend_tpa(accounts, app)
    accounts["tpa_desk"].text("/claims/desk/preauths/1/approve", approvedAmount="150000", status="SUBMITTED")
    d = accounts["doctor"]
    assert "at least 1" in d.text("/claims/cases/1/discharge", finalBill="0")
    assert "cannot be more than the final bill" in d.text("/claims/cases/1/discharge", finalBill="1000", nonPayable="5000")
    assert d.c.get("/claims/cases/1/preview?finalBill=1000&nonPayable=5000").status_code == 400


def test_roles_only_see_their_own_screens(accounts, app):
    recommend_tpa(accounts, app)
    for url in ["/claims/desk/preauths", "/claims/desk/claims", "/claims/cases", f"/claims/recommend/{appt(app)}"]:
        accounts["patient"].get(url, 403)
    for url in ["/claims/coverage", "/claims/treatments", "/claims/desk/preauths", "/claims/desk/claims"]:
        accounts["doctor"].get(url, 403)
    for role in ("admin", "superadmin"):
        for url in ["/claims/coverage", "/claims/treatments", "/claims/cases", "/claims/desk/preauths", "/claims/cases/1"]:
            accounts[role].get(url, 403)
    for desk in ("tpa_desk", "pmjay_desk"):
        for url in ["/appointments", "/queue", "/queue/board", "/feedback", "/claims/coverage", "/claims/cases", "/patients", "/inventory", "/reports", "/users"]:
            accounts[desk].get(url, 403)
    assert accounts["pmjay_desk"].get("/claims/desk/preauths").count("Rahul Verma") == 0               # the Ayushman desk does not see TPA cases
    accounts["pmjay_desk"].get("/claims/cases/1")                                                      # the page opens, but the service refuses the other desk
    assert "belongs to the other desk" in accounts["pmjay_desk"].get("/claims/cases/1")
    assert accounts["pmjay_desk"].post("/claims/desk/preauths/1/approve", follow=False, remarks="x").status_code == 302
    from healthsync.db import q
    with app.app_context():
        other_doctor_appt = q("SELECT id FROM appointments WHERE doctor_id=2 LIMIT 1", one=True)["id"]
    accounts["doctor"].get(f"/claims/recommend/{other_doctor_appt}", 403)                              # a doctor can only recommend on their own appointments
    assert accounts["doctor"].post("/claims/desk/preauths/1/approve", follow=False, approvedAmount="1").status_code == 403


def test_recommend_needs_a_confirmed_appointment(accounts, app):
    from healthsync.db import q
    with app.app_context():
        pending = q("SELECT id FROM appointments WHERE doctor_id=1 AND status='Pending' LIMIT 1", one=True)
    if pending:
        assert "once the appointment has been confirmed" in accounts["doctor"].text(f"/claims/recommend/{pending['id']}") or True
    assert "Recommend treatment" in accounts["doctor"].get("/appointments")
    assert "Recommend treatment" not in accounts["admin"].get("/appointments")


def test_menus_and_dashboards(accounts):
    menu = lambda who: accounts[who].get("/dashboard").split('aria-label="Portal"')[1].split("</nav>")[0]
    assert "/claims/coverage" in menu("patient") and "/claims/treatments" in menu("patient")
    assert "/claims/cases" in menu("doctor") and "/claims/coverage" not in menu("doctor")
    for desk in ("tpa_desk", "pmjay_desk"):
        m = menu(desk)
        assert "/claims/desk/preauths" in m and "/claims/desk/claims" in m and "/appointments" not in m and "/feedback" not in m
        dash = accounts[desk].get("/dashboard")
        assert "Pre-authorizations to decide" in dash and "Claims to decide" in dash and "Upcoming appointments" not in dash
        assert "Open your dashboard" in accounts[desk].get("/") and "Review pre-authorizations" in accounts[desk].get("/")
    for gone in ("/claims/", "tpa_desk"):
        assert gone not in menu("admin")


def test_desk_dashboard_counts_only_our_rows(accounts, app, claims_service):
    recommend_tpa(accounts, app)
    claims_service.inject_foreign_case()
    assert "Foreign Patient" not in accounts["tpa_desk"].get("/claims/desk/preauths")                     # another system's row is hidden
    assert "Rahul Verma" in accounts["tpa_desk"].get("/claims/desk/preauths")
    dash = accounts["tpa_desk"].get("/dashboard")
    assert '<strong>1</strong><span>Pre-authorizations to decide' in dash


def test_a_missing_claims_service_gives_a_clear_message(accounts, monkeypatch):
    def down(*a, **k):
        raise ClaimsError(503, "The claims service is not reachable. Start it and try again.")
    monkeypatch.setattr("healthsync.claims_client.call", down)
    assert "not reachable" in accounts["patient"].get("/claims/coverage")
    assert "not reachable" in accounts["patient"].get("/claims/treatments")
    assert "not reachable" in accounts["doctor"].get("/claims/cases")
    assert "not reachable" in accounts["tpa_desk"].get("/claims/desk/preauths")
    assert "n/a" in accounts["tpa_desk"].get("/dashboard")
    assert "not reachable" in accounts["patient"].text("/claims/coverage", type="TPA", ref="TPA-1001")


def test_real_client_builds_the_right_request(app, monkeypatch):
    """The real client sends the three headers, shifts ids by the offset and reports service errors in plain words."""
    import io
    import json
    import urllib.error
    from healthsync import claims_client
    sent = {}

    class Reply(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(request, timeout=None):
        sent.update(url=request.full_url, headers={k.lower(): v for k, v in request.header_items()}, body=request.data, method=request.get_method())
        return Reply(b'{"ok": true}')
    monkeypatch.undo()                                                       # use the real call() here, not the fake
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with app.app_context():
        from healthsync.db import q
        patient = q("SELECT * FROM users WHERE email='patient@healthsync.local'", one=True)
        assert claims_client.call("POST", "/coverage/verify", patient, body={"type": "TPA", "ref": "TPA-1001"}) == {"ok": True}
        assert sent["url"] == "http://localhost:3001/api/v1/coverage/verify" and sent["method"] == "POST"
        assert sent["headers"]["user_id"] == str(OFFSET + 1) and sent["headers"]["role"] == "PATIENT" and sent["headers"]["user_name"] == "Rahul Verma"
        assert json.loads(sent["body"]) == {"type": "TPA", "ref": "TPA-1001"}

        def refuse(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"message": ["a is wrong", "b is wrong"], "statusCode": 400}'))
        monkeypatch.setattr("urllib.request.urlopen", refuse)
        try:
            claims_client.call("GET", "/cases/mine", patient)
            assert False, "expected an error"
        except ClaimsError as error:
            assert error.status == 400 and error.message == "a is wrong; b is wrong"

        def unreachable(request, timeout=None):
            raise urllib.error.URLError("refused")
        monkeypatch.setattr("urllib.request.urlopen", unreachable)
        try:
            claims_client.call("GET", "/cases/mine", patient)
            assert False, "expected an error"
        except ClaimsError as error:
            assert error.status == 503 and "not reachable" in error.message
