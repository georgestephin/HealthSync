"""Insurance claims screens (TPA and Ayushman).

HealthSync only shows the screens and relays actions. The separate Claims service owns the coverage, case,
pre-authorization and claim data, and does every calculation. See claims_client.py for how it is called."""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from .. import claims_client
from ..claims_client import ClaimsError
from ..constants import DESK_TITLES, DESKS
from ..db import q
from ..live import page as live_page
from ..security import current_user, login_required
from ..services import my_doctor

bp = Blueprint("claims", __name__, url_prefix="/claims")

CASE_VIEWERS = ("patient", "doctor", *DESKS)
PREAUTH_STATUSES = ("SUBMITTED", "QUERY", "APPROVED", "REJECTED")
CLAIM_STATUSES = ("SUBMITTED", "SETTLED", "REJECTED")


# ------------------------------------------------------------------ helpers for the templates
def inr(value):
    """Whole rupees in Indian grouping: 150000 -> ₹1,50,000."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "–"
    digits = str(abs(number))
    if len(digits) > 3:
        head, tail, groups = digits[:-3], digits[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join(([head] if head else []) + groups + [tail])
    return f"{'-' if number < 0 else ''}₹{digits}"


def stamp(value):
    return value[:16].replace("T", " ") if value else "–"


def case_status(case):
    """The label, colour and extra note for a case, following the status table of the claims guide."""
    pre, claim = case.get("preauth") or {}, case.get("claim") or {}
    status, pre_status, claim_status = case["status"], pre.get("status"), claim.get("status")
    if status == "REQUESTED" and pre_status == "QUERY":
        return dict(label="Query from desk", tone="pending", note=pre.get("deskRemarks"))
    if status == "REQUESTED":
        return dict(label="Waiting for approval", tone="pending", note=None)
    if status == "ADMITTED" and pre_status == "APPROVED":
        return dict(label="Approved and admitted", tone="confirmed", note=None)
    if status == "ADMITTED":
        return dict(label="Emergency admission, approval pending", tone="pending", note=None)
    if status == "DISCHARGED":
        return dict(label="Discharged, claim submitted", tone="completed", note=None)
    if status == "CLOSED" and claim_status == "SETTLED":
        return dict(label="Settled", tone="confirmed", note=None)
    if status == "CLOSED" and claim_status == "REJECTED":
        return dict(label="Claim rejected", tone="cancelled", note=claim.get("rejectionReason"))
    if status == "REJECTED":
        return dict(label="Pre-auth rejected", tone="cancelled", note=pre.get("deskRemarks"))
    return dict(label=status.title(), tone="", note=None)


def case_steps(case):
    """The five-step progress bar: Requested, Approved, Admitted, Discharged, Settled."""
    pre, claim = case.get("preauth") or {}, case.get("claim") or {}
    status = case["status"]
    done = [True, pre.get("status") == "APPROVED", status in ("ADMITTED", "DISCHARGED", "CLOSED"),
            status in ("DISCHARGED", "CLOSED"), claim.get("status") == "SETTLED"]
    stopped = status == "REJECTED" or (status == "CLOSED" and claim.get("status") == "REJECTED")
    current = next((i for i, flag in enumerate(done) if not flag), None)
    labels = ["Requested", "Approved", "Admitted", "Discharged", "Settled"]
    return [dict(label=label, state="done" if done[i] else ("current" if i == current and not stopped else "todo")) for i, label in enumerate(labels)]


bp.add_app_template_filter(inr, "inr")
bp.add_app_template_filter(stamp, "stamp")
bp.add_app_template_global(case_status)
bp.add_app_template_global(case_steps)


# ------------------------------------------------------------------ small utilities
def api(method, path, **kwargs):
    return claims_client.call(method, path, current_user(), **kwargs)


def fetch(method, path, **kwargs):
    """Returns (data, error). A problem reaching the Claims service becomes a message the page can show."""
    try:
        return api(method, path, **kwargs), None
    except ClaimsError as error:
        return None, error.message


def whole(text):
    """A whole number from form text, or None."""
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


# ------------------------------------------------------------------ patient pages
@bp.route("/coverage", methods=["GET", "POST"])
@login_required("patient")
def coverage():
    form, error = {}, None
    if request.method == "POST":
        form = dict(type=request.form.get("type", "TPA"), ref=(request.form.get("ref") or "").strip())
        if form["type"] not in ("TPA", "AYUSHMAN"):
            abort(400)
        if not form["ref"]:
            error = "Enter your policy number or card number."
        else:
            try:
                api("POST", "/coverage/verify", body={"type": form["type"], "ref": form["ref"]})
                flash("Coverage verified and saved.", "ok")
                return redirect(url_for("claims.coverage"))
            except ClaimsError as problem:
                error = problem.message
    cov = None
    try:
        cov = api("GET", "/coverage/me")
    except ClaimsError as problem:
        if problem.status != 404 and not error:      # 404 simply means nothing is verified yet
            error = problem.message
    return render_template("claims/coverage.html", cov=cov, error=error, form=form)


@bp.route("/treatments")
@login_required("patient")
def treatments():
    cases, error = fetch("GET", "/cases/mine")
    return live_page("claims/treatments.html", fragment="claims/_treatments_live.html", cases=cases or [], error=error)


@bp.route("/cases/<int:case_id>")
@login_required(*CASE_VIEWERS)
def case_detail(case_id):
    case, error = fetch("GET", f"/cases/{case_id}")
    return live_page("claims/case.html", fragment="claims/_case_live.html", case=case, error=error, case_id=case_id)


# ------------------------------------------------------------------ doctor pages
@bp.route("/recommend/<int:appointment_id>", methods=["GET", "POST"])
@login_required("doctor")
def recommend(appointment_id):
    doctor = my_doctor(current_user())
    appt = q("SELECT a.id, a.patient_id, a.doctor_id, a.date, a.time, a.status, p.name AS patient FROM appointments a "
             "JOIN patients p ON p.id=a.patient_id WHERE a.id=?", (appointment_id,), one=True) or abort(404)
    if not doctor or appt["doctor_id"] != doctor["id"]:
        abort(403)
    if appt["status"] not in ("Confirmed", "Completed"):
        flash("You can recommend treatment once the appointment has been confirmed.", "error")
        return redirect(url_for("appointments.index"))
    offset = claims_client.offset()
    cov, error = None, None
    try:
        cov = api("GET", f"/coverage/patient/{offset + appt['patient_id']}")
    except ClaimsError as problem:
        if problem.status != 404:                    # 404 = no coverage, so the patient is self-pay
            error = problem.message
    packages = []
    if cov and cov["coverageType"] == "AYUSHMAN":
        packages, problem = fetch("GET", "/packages")
        packages, error = packages or [], error or problem
    values, errors = {}, {}
    if request.method == "POST" and cov:
        values = {key: (request.form.get(key) or "").strip() for key in ("diagnosis", "estimatedCost", "packageCode")}
        values["emergency"] = bool(request.form.get("emergency"))
        body = dict(appointmentId=offset + appt["id"], patientId=offset + appt["patient_id"], patientName=appt["patient"],
                    diagnosis=values["diagnosis"], isEmergency=values["emergency"])
        if not values["diagnosis"]:
            errors["diagnosis"] = "Diagnosis is required."
        if cov["coverageType"] == "TPA":
            cost = whole(values["estimatedCost"])
            if cost is None or cost < 1:
                errors["estimatedCost"] = "Enter the estimated cost as a whole number of rupees."
            else:
                body["estimatedCost"] = cost
        elif values["packageCode"] not in {p["code"] for p in packages}:
            errors["packageCode"] = "Choose a package."
        else:
            body["packageCode"] = values["packageCode"]
        if not errors:
            try:
                api("POST", "/cases/create", body=body)
                flash("Treatment recommended. The insurance desk has been asked for pre-authorization.", "ok")
                return redirect(url_for("claims.cases"))
            except ClaimsError as problem:
                error = problem.message
    return render_template("claims/recommend.html", appt=appt, cov=cov, packages=packages, values=values, errors=errors, error=error)


@bp.route("/cases")
@login_required("doctor")
def cases():
    rows, error = fetch("GET", "/cases/doctor")
    return live_page("claims/cases.html", fragment="claims/_cases_live.html", cases=rows or [], error=error)


@bp.post("/preauths/<int:preauth_id>/reply")
@login_required("doctor")
def reply(preauth_id):
    text = (request.form.get("reply") or "").strip()
    if not text:
        flash("Write a reply before sending it.", "error")
    else:
        try:
            api("POST", f"/preauths/{preauth_id}/resubmit", body={"reply": text})
            flash("Reply sent to the desk.", "ok")
        except ClaimsError as problem:
            flash(problem.message, "error")
    return redirect(url_for("claims.cases"))


@bp.route("/cases/<int:case_id>/discharge", methods=["GET", "POST"])
@login_required("doctor")
def discharge(case_id):
    case, error = fetch("GET", f"/cases/{case_id}")
    values, errors = {}, {}
    if case and case["status"] != "ADMITTED":
        error = f"This case is {case['status'].lower()}, so it cannot be discharged."
    if request.method == "POST" and case and case["status"] == "ADMITTED":
        values = dict(finalBill=(request.form.get("finalBill") or "").strip(), nonPayable=(request.form.get("nonPayable") or "").strip())
        bill, non_payable = whole(values["finalBill"]), whole(values["nonPayable"] or "0")
        if bill is None or bill < 1:
            errors["finalBill"] = "Enter the final bill as a whole number, at least 1."
        if non_payable is None:
            errors["nonPayable"] = "Enter a whole number, or leave it empty."
        elif bill and non_payable > bill:
            errors["nonPayable"] = "Non-payable items cannot be more than the final bill."
        if not errors:
            try:
                api("POST", f"/cases/{case_id}/discharge", body={"finalBill": bill, "nonPayableAmount": non_payable})
                flash("Patient discharged and the claim has been submitted.", "ok")
                return redirect(url_for("claims.case_detail", case_id=case_id))
            except ClaimsError as problem:
                error = problem.message
    return render_template("claims/discharge.html", case=case, values=values, errors=errors, error=error)


@bp.get("/cases/<int:case_id>/preview")
@login_required("doctor")
def preview(case_id):
    """Who pays what for the typed amounts. Nothing is saved. Used by the discharge page while typing."""
    bill, non_payable = whole(request.args.get("finalBill")), whole(request.args.get("nonPayable") or "0")
    if bill is None or bill < 1 or non_payable is None:
        return jsonify(error="Enter whole numbers only."), 400
    if non_payable > bill:
        return jsonify(error="Non-payable items cannot be more than the final bill."), 400
    try:
        return jsonify(api("GET", f"/cases/{case_id}/claim-preview", params=dict(finalBill=bill, nonPayable=non_payable)))
    except ClaimsError as problem:
        return jsonify(error=problem.message), (problem.status if 400 <= problem.status < 500 else 502)


# ------------------------------------------------------------------ desk pages (TPA desk and Ayushman desk)
def _back(endpoint):
    return redirect(url_for(endpoint, status=request.form.get("status") or None))


def _post(path, body, done, endpoint):
    try:
        api("POST", path, **({"body": body} if body is not None else {}))
        flash(done, "ok")
    except ClaimsError as problem:
        flash(problem.message, "error")
    return _back(endpoint)


@bp.route("/desk/preauths")
@login_required(*DESKS)
def desk_preauths():
    status = request.args.get("status", "SUBMITTED")
    if status not in PREAUTH_STATUSES + ("ALL",):
        status = "SUBMITTED"
    rows, error = fetch("GET", "/desk/preauths", params={"status": None if status == "ALL" else status})
    return live_page("claims/desk_preauths.html", fragment="claims/_desk_preauths_live.html", rows=claims_client.ours(rows or []),
                     status=status, statuses=PREAUTH_STATUSES, error=error, title=DESK_TITLES[current_user()["role"]])


@bp.post("/desk/preauths/<int:preauth_id>/approve")
@login_required(*DESKS)
def desk_approve(preauth_id):
    body = {"remarks": (request.form.get("remarks") or "").strip() or "Approved"}
    if current_user()["role"] == "tpa_desk":         # the Ayushman desk approves the fixed package price, so no amount
        amount = whole(request.form.get("approvedAmount"))
        if amount is None or amount < 1:
            flash("Enter the approved amount as a whole number of rupees.", "error")
            return _back("claims.desk_preauths")
        body["approvedAmount"] = amount
    return _post(f"/desk/preauths/{preauth_id}/approve", body, "Pre-authorization approved.", "claims.desk_preauths")


@bp.post("/desk/preauths/<int:preauth_id>/query")
@login_required(*DESKS)
def desk_query(preauth_id):
    remarks = (request.form.get("remarks") or "").strip()
    if not remarks:
        flash("Write what you need from the hospital.", "error")
        return _back("claims.desk_preauths")
    return _post(f"/desk/preauths/{preauth_id}/query", {"remarks": remarks}, "Query sent to the hospital.", "claims.desk_preauths")


@bp.post("/desk/preauths/<int:preauth_id>/reject")
@login_required(*DESKS)
def desk_reject(preauth_id):
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("Write the reason for rejecting.", "error")
        return _back("claims.desk_preauths")
    return _post(f"/desk/preauths/{preauth_id}/reject", {"reason": reason}, "Pre-authorization rejected.", "claims.desk_preauths")


@bp.route("/desk/claims")
@login_required(*DESKS)
def desk_claims():
    status = request.args.get("status", "SUBMITTED")
    if status not in CLAIM_STATUSES + ("ALL",):
        status = "SUBMITTED"
    rows, error = fetch("GET", "/desk/claims", params={"status": None if status == "ALL" else status})
    return live_page("claims/desk_claims.html", fragment="claims/_desk_claims_live.html", rows=claims_client.ours(rows or []),
                     status=status, statuses=CLAIM_STATUSES, error=error, title=DESK_TITLES[current_user()["role"]])


@bp.post("/desk/claims/<int:claim_id>/settle")
@login_required(*DESKS)
def desk_settle(claim_id):
    return _post(f"/desk/claims/{claim_id}/settle", None, "Claim settled.", "claims.desk_claims")


@bp.post("/desk/claims/<int:claim_id>/reject")
@login_required(*DESKS)
def desk_reject_claim(claim_id):
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("Write the reason for rejecting.", "error")
        return _back("claims.desk_claims")
    return _post(f"/desk/claims/{claim_id}/reject", {"reason": reason}, "Claim rejected.", "claims.desk_claims")
