"""An in-memory stand-in for the Claims service that follows the claims guide, so tests need no real service."""
import re
from datetime import date
from healthsync import claims_client
from healthsync.claims_client import ClaimsError

NOW = "2026-11-01T10:00:00.000Z"


class FakeClaims:
    def __init__(self):
        self.log, self.coverage = [], {}
        self.policies = {
            "TPA-1001": dict(holderName="Rahul Mehta", insurerName="Star Health", tpaName="Medi Assist", sumInsured=500000, balance=500000, coPayPercent=10, validTill="2099-12-31"),
            "TPA-1002": dict(holderName="Old Policy", insurerName="Star Health", tpaName="Medi Assist", sumInsured=300000, balance=300000, coPayPercent=20, validTill="2020-01-01"),
        }
        self.families = {"FAM-001": dict(headName="Ramesh Yadav", annualLimit=500000, usedAmount=0)}
        self.cards = {"PMJAY-1001": ("FAM-001", "Ramesh Yadav"), "PMJAY-1002": ("FAM-001", "Geeta Yadav")}
        self.packages = [dict(id=1, code="GS-001", name="Appendectomy", specialty="General Surgery", rate=25000, expectedDays=3),
                         dict(id=2, code="OR-001", name="Knee replacement", specialty="Orthopedics", rate=90000, expectedDays=5)]
        self.cases, self.preauths, self.claims, self.ids = {}, {}, {}, dict(case=0, pre=0, claim=0)
        D, P, A, S = "DOCTOR", "PATIENT", ("TPA_DESK", "PMJAY_DESK"), ("TPA_DESK", "PMJAY_DESK")
        self.routes = [
            ("POST", r"/coverage/verify", (P,), self.verify), ("GET", r"/coverage/me", (P,), self.me), ("GET", r"/coverage/patient/(\d+)", (D,), self.patient_coverage),
            ("GET", r"/packages", (D, "PMJAY_DESK"), lambda *a: self.packages), ("POST", r"/cases/create", (D,), self.create),
            ("GET", r"/cases/mine", (P,), self.mine), ("GET", r"/cases/doctor", (D,), self.doctor_cases), ("GET", r"/cases/(\d+)", (P, D) + S, self.get_case),
            ("GET", r"/cases/(\d+)/claim-preview", (D,), self.preview), ("POST", r"/cases/(\d+)/discharge", (D,), self.discharge),
            ("POST", r"/preauths/(\d+)/resubmit", (D,), self.resubmit), ("GET", r"/desk/preauths", S, self.desk_preauths),
            ("POST", r"/desk/preauths/(\d+)/approve", S, self.approve), ("POST", r"/desk/preauths/(\d+)/query", S, self.query), ("POST", r"/desk/preauths/(\d+)/reject", S, self.reject),
            ("GET", r"/desk/claims", S, self.desk_claims), ("POST", r"/desk/claims/(\d+)/settle", S, self.settle), ("POST", r"/desk/claims/(\d+)/reject", S, self.reject_claim)]

    # -- entry point used instead of healthsync.claims_client.call
    def __call__(self, method, path, user, body=None, params=None):
        role, uid, name = claims_client.identity(user)
        self.log.append((method, path, role, uid))
        for verb, pattern, roles, handler in self.routes:
            match = re.fullmatch(pattern, path)
            if verb == method and match:
                if role not in roles:
                    raise ClaimsError(403, "Insufficient permissions")
                return handler(role, uid, name, body or {}, params or {}, *[int(g) for g in match.groups()])
        raise ClaimsError(404, "Not found")

    # -- coverage
    def summary(self, uid):
        kind, ref = self.coverage[uid]
        if kind == "TPA":
            p = self.policies[ref]
            return dict(coverageType="TPA", coverageRef=ref, isActive=True, inactiveReason=None, **p)
        fam_id, member = self.cards[ref]
        f = self.families[fam_id]
        return dict(coverageType="AYUSHMAN", coverageRef=ref, memberName=member, familyId=fam_id, headName=f["headName"], annualLimit=f["annualLimit"], usedAmount=f["usedAmount"],
                    remaining=f["annualLimit"] - f["usedAmount"], members=[dict(name=n, cardNo=c) for c, (fi, n) in self.cards.items() if fi == fam_id])

    def verify(self, role, uid, name, body, params):
        kind, ref = body.get("type"), body.get("ref")
        if kind == "TPA":
            policy = self.policies.get(ref)
            if not policy:
                raise ClaimsError(404, "Policy not found")
            if policy["validTill"] < date.today().isoformat():
                raise ClaimsError(400, "Policy has expired")
            if policy["balance"] <= 0:
                raise ClaimsError(400, "Policy balance is exhausted")
        elif kind == "AYUSHMAN":
            if ref not in self.cards:
                raise ClaimsError(404, "Card not found. The patient is not eligible.")
        else:
            raise ClaimsError(400, "type must be TPA or AYUSHMAN")
        self.coverage[uid] = (kind, ref)
        return self.summary(uid)

    def me(self, role, uid, name, body, params):
        if uid not in self.coverage:
            raise ClaimsError(404, "No coverage on file for this patient")
        return self.summary(uid)

    def patient_coverage(self, role, uid, name, body, params, patient_id):
        if patient_id not in self.coverage:
            raise ClaimsError(404, "No coverage on file for this patient")
        return self.summary(patient_id)

    # -- cases
    def view(self, case):
        pre = dict(self.preauths[case["id"]])
        claim = next((dict(c) for c in self.claims.values() if c["caseId"] == case["id"]), None)
        return dict(case, preauth=pre, claim=claim)

    def check_access(self, role, uid, case):
        if role == "PATIENT" and case["patientId"] != uid:
            raise ClaimsError(403, "This case belongs to another patient")
        if role == "DOCTOR" and case["doctorId"] != uid:
            raise ClaimsError(403, "This case belongs to another doctor")
        if role in ("TPA_DESK", "PMJAY_DESK") and case["payerType"] != ("TPA" if role == "TPA_DESK" else "AYUSHMAN"):
            raise ClaimsError(403, "This case belongs to the other desk")

    def find(self, case_id):
        if case_id not in self.cases:
            raise ClaimsError(404, "Case not found")
        return self.cases[case_id]

    def create(self, role, uid, name, body, params):
        covered = self.coverage.get(body.get("patientId"))
        if not covered:
            raise ClaimsError(400, "Patient has no verified coverage")
        if any(c["appointmentId"] == body["appointmentId"] and c["status"] not in ("REJECTED", "CLOSED") for c in self.cases.values()):
            raise ClaimsError(409, "This appointment already has an active treatment case")
        kind, ref = covered
        package = None
        if kind == "TPA":
            cost = body.get("estimatedCost")
            if not cost:
                raise ClaimsError(400, "estimatedCost is required for a TPA patient")
            if cost > self.policies[ref]["balance"]:
                raise ClaimsError(400, "Estimated cost is above the policy balance")
        else:
            package = next((p for p in self.packages if p["code"] == body.get("packageCode")), None)
            if not package:
                raise ClaimsError(400, "Package not found")
            fam = self.families[self.cards[ref][0]]
            if fam["annualLimit"] - fam["usedAmount"] < package["rate"]:
                raise ClaimsError(400, "Family balance is too low for this package")
            cost = package["rate"]
        self.ids["case"] += 1
        self.ids["pre"] += 1
        cid, emergency = self.ids["case"], bool(body.get("isEmergency"))
        case = dict(id=cid, appointmentId=body["appointmentId"], patientId=body["patientId"], patientName=body["patientName"], doctorId=uid, doctorName=name,
                    diagnosis=body["diagnosis"], payerType=kind, coverageRef=ref, packageCode=package and package["code"], estimatedCost=cost, isEmergency=emergency,
                    status="ADMITTED" if emergency else "REQUESTED", createdAt=NOW, updatedAt=NOW)
        self.cases[cid] = case
        self.preauths[cid] = dict(id=self.ids["pre"], caseId=cid, status="SUBMITTED", requestedAmount=cost, approvedAmount=None, deskRemarks=None, hospitalReply=None,
                                  postApprovalDue="2026-11-02T10:00:00.000Z" if emergency else None, createdAt=NOW, updatedAt=NOW)
        return self.view(case)

    def inject_foreign_case(self, patient_id=7):
        """A case created by another system that shares the claims database (its patient id is below our offset)."""
        self.ids["case"] += 1
        self.ids["pre"] += 1
        cid = self.ids["case"]
        self.cases[cid] = dict(id=cid, appointmentId=999, patientId=patient_id, patientName="Foreign Patient", doctorId=3, doctorName="Dr. Elsewhere", diagnosis="Foreign case",
                               payerType="TPA", coverageRef="TPA-1001", packageCode=None, estimatedCost=1000, isEmergency=False, status="REQUESTED", createdAt=NOW, updatedAt=NOW)
        self.preauths[cid] = dict(id=self.ids["pre"], caseId=cid, status="SUBMITTED", requestedAmount=1000, approvedAmount=None, deskRemarks=None, hospitalReply=None,
                                  postApprovalDue=None, createdAt=NOW, updatedAt=NOW)

    def mine(self, role, uid, name, body, params):
        return [self.view(c) for c in sorted(self.cases.values(), key=lambda c: -c["id"]) if c["patientId"] == uid]

    def doctor_cases(self, role, uid, name, body, params):
        return [self.view(c) for c in sorted(self.cases.values(), key=lambda c: -c["id"]) if c["doctorId"] == uid]

    def get_case(self, role, uid, name, body, params, case_id):
        case = self.find(case_id)
        self.check_access(role, uid, case)
        return self.view(case)

    # -- money
    def split(self, case, final, non_payable):
        pre = self.preauths[case["id"]]
        if case["payerType"] == "AYUSHMAN":
            return case["estimatedCost"], 0, case["estimatedCost"]
        policy = self.policies[case["coverageRef"]]
        approved = pre["approvedAmount"] if pre["approvedAmount"] is not None else pre["requestedAmount"]
        payer = min(round(min(final - non_payable, approved) * (100 - policy["coPayPercent"]) / 100), policy["balance"])
        return payer, final - payer, approved

    def preview(self, role, uid, name, body, params, case_id):
        case = self.find(case_id)
        self.check_access(role, uid, case)
        if case["status"] != "ADMITTED":
            raise ClaimsError(400, "Only an admitted case can be discharged")
        final, non = int(params["finalBill"]), int(params.get("nonPayable") or 0)
        payer, patient, approved = self.split(case, final, non)
        policy = self.policies.get(case["coverageRef"], {})
        return dict(caseId=case_id, payerType=case["payerType"], finalBill=final, nonPayableAmount=non, approvedAmount=approved, coPayPercent=policy.get("coPayPercent", 0),
                    payerAmount=payer, patientAmount=patient, provisional=self.preauths[case_id]["status"] != "APPROVED")

    def discharge(self, role, uid, name, body, params, case_id):
        case = self.find(case_id)
        self.check_access(role, uid, case)
        if case["status"] != "ADMITTED":
            raise ClaimsError(400, "Only an admitted case can be discharged")
        if any(c["caseId"] == case_id for c in self.claims.values()):
            raise ClaimsError(409, "A claim already exists for this case")
        final, non = body["finalBill"], body.get("nonPayableAmount", 0)
        payer, patient, _ = self.split(case, final, non)
        self.ids["claim"] += 1
        self.claims[self.ids["claim"]] = dict(id=self.ids["claim"], caseId=case_id, finalBill=final, nonPayableAmount=non, payerAmount=payer, patientAmount=patient,
                                               status="SUBMITTED", rejectionReason=None, submittedAt=NOW, settledAt=None)
        case["status"] = "DISCHARGED"
        return self.view(case)

    # -- pre-authorizations
    def preauth(self, pre_id):
        pre = next((p for p in self.preauths.values() if p["id"] == pre_id), None)
        if not pre:
            raise ClaimsError(404, "Pre-authorization not found")
        return pre, self.cases[pre["caseId"]]

    def resubmit(self, role, uid, name, body, params, pre_id):
        pre, case = self.preauth(pre_id)
        self.check_access(role, uid, case)
        if pre["status"] != "QUERY":
            raise ClaimsError(400, f"There is nothing to reply to. The status is {pre['status']}.")
        pre.update(status="SUBMITTED", hospitalReply=body["reply"])
        return dict(pre)

    def desk_preauths(self, role, uid, name, body, params):
        kind = "TPA" if role == "TPA_DESK" else "AYUSHMAN"
        rows = [dict(p, case=self.view(self.cases[p["caseId"]]), isOverdue=False) for p in sorted(self.preauths.values(), key=lambda p: -p["id"])
                if self.cases[p["caseId"]]["payerType"] == kind and (not params.get("status") or p["status"] == params["status"])]
        return rows

    def approve(self, role, uid, name, body, params, pre_id):
        pre, case = self.preauth(pre_id)
        self.check_access(role, uid, case)
        if pre["status"] != "SUBMITTED":
            raise ClaimsError(400, "Only a submitted pre-authorization can be approved")
        if role == "TPA_DESK":
            amount = body.get("approvedAmount")
            if not amount:
                raise ClaimsError(400, "approvedAmount is required")
            if amount > pre["requestedAmount"] or amount > self.policies[case["coverageRef"]]["balance"]:
                raise ClaimsError(400, "The approved amount is above the requested amount or the policy balance")
        else:
            amount = case["estimatedCost"]
        pre.update(status="APPROVED", approvedAmount=amount, deskRemarks=body.get("remarks"))
        if case["status"] == "REQUESTED":
            case["status"] = "ADMITTED"
        return dict(pre, case=self.view(case))

    def query(self, role, uid, name, body, params, pre_id):
        pre, case = self.preauth(pre_id)
        self.check_access(role, uid, case)
        if pre["status"] != "SUBMITTED":
            raise ClaimsError(400, "A query can only be raised while the pre-authorization is submitted")
        pre.update(status="QUERY", deskRemarks=body["remarks"])
        return dict(pre)

    def reject(self, role, uid, name, body, params, pre_id):
        pre, case = self.preauth(pre_id)
        self.check_access(role, uid, case)
        if pre["status"] not in ("SUBMITTED", "QUERY"):
            raise ClaimsError(400, "Only a submitted or queried pre-authorization can be rejected")
        pre.update(status="REJECTED", deskRemarks=body["reason"])
        case["status"] = "REJECTED"
        for claim in self.claims.values():
            if claim["caseId"] == case["id"] and claim["status"] == "SUBMITTED":
                claim.update(status="REJECTED", rejectionReason="The pre-authorization was rejected", payerAmount=0, patientAmount=claim["finalBill"])
        return dict(pre)

    # -- claims
    def desk_claims(self, role, uid, name, body, params):
        kind = "TPA" if role == "TPA_DESK" else "AYUSHMAN"
        return [dict(c, case=self.view(self.cases[c["caseId"]]), preauthStatus=self.preauths[c["caseId"]]["status"]) for c in sorted(self.claims.values(), key=lambda c: -c["id"])
                if self.cases[c["caseId"]]["payerType"] == kind and (not params.get("status") or c["status"] == params["status"])]

    def settle(self, role, uid, name, body, params, claim_id):
        claim = self.claims[claim_id]
        case = self.cases[claim["caseId"]]
        self.check_access(role, uid, case)
        if claim["status"] != "SUBMITTED":
            raise ClaimsError(400, "The claim is not submitted")
        if self.preauths[case["id"]]["status"] != "APPROVED":
            raise ClaimsError(400, "The pre-authorization must be approved before the claim can be settled")
        payer, patient, _ = self.split(case, claim["finalBill"], claim["nonPayableAmount"])
        if case["payerType"] == "TPA":
            self.policies[case["coverageRef"]]["balance"] -= payer
        else:
            self.families[self.cards[case["coverageRef"]][0]]["usedAmount"] += payer
        claim.update(status="SETTLED", payerAmount=payer, patientAmount=patient, settledAt=NOW)
        case["status"] = "CLOSED"
        return dict(claim)

    def reject_claim(self, role, uid, name, body, params, claim_id):
        claim = self.claims[claim_id]
        case = self.cases[claim["caseId"]]
        self.check_access(role, uid, case)
        if claim["status"] != "SUBMITTED":
            raise ClaimsError(400, "The claim is not submitted")
        claim.update(status="REJECTED", rejectionReason=body["reason"], payerAmount=0, patientAmount=claim["finalBill"])
        case["status"] = "CLOSED"
        return dict(claim)
