"""Client for the separate Claims service (NestJS, default http://localhost:3001/api/v1).

The Claims service has no tokens: it trusts three headers (user_id, role, user_name), so only this server
should ever call it. Patient and doctor ids are shifted by CLAIMS_ID_OFFSET so they cannot clash with
other systems that share the same claims database."""
import json
import urllib.error
import urllib.parse
import urllib.request
from flask import current_app
from .constants import CLAIMS_ROLE
from .services import my_doctor, my_patient


class ClaimsError(Exception):
    """A problem reported by (or reaching) the Claims service. `message` is safe to show to the user."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def offset():
    return current_app.config["CLAIMS_ID_OFFSET"]


def identity(user):
    """The (role, user_id, user_name) headers for this HealthSync user."""
    role = user["role"]
    if role not in CLAIMS_ROLE:
        raise ClaimsError(403, "Your account has no access to insurance claims.")
    if role == "patient":
        uid = offset() + my_patient(user)
    elif role == "doctor":
        doctor = my_doctor(user)
        if not doctor:
            raise ClaimsError(403, "Your login is not linked to a doctor profile. Ask an admin to link it.")
        uid = offset() + doctor["id"]
    else:
        uid = user["id"]
    return CLAIMS_ROLE[role], uid, user["name"]


def _message(error):
    try:
        message = json.loads(error.read().decode() or "{}").get("message")
    except (ValueError, AttributeError):
        message = None
    if isinstance(message, list):
        message = "; ".join(str(m) for m in message)
    return message or f"The claims service returned an error ({error.code})."


def call(method, path, user, *, body=None, params=None):
    """Call the Claims service as `user` and return the parsed JSON. Raises ClaimsError on any problem."""
    role, uid, name = identity(user)
    url = current_app.config["CLAIMS_API_URL"].rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    headers = {"user_id": str(uid), "role": role, "user_name": name.encode("latin-1", "replace").decode("latin-1")}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=current_app.config["CLAIMS_TIMEOUT"]) as response:
            return json.loads(response.read().decode() or "null")
    except urllib.error.HTTPError as error:
        raise ClaimsError(error.code, _message(error)) from None
    except ValueError:
        raise ClaimsError(502, "The claims service sent a reply that could not be read.") from None
    except OSError:
        raise ClaimsError(503, f"The claims service is not reachable. Start it ({current_app.config['CLAIMS_API_URL']}) and try again.") from None


def ours(rows):
    """Desk lists: keep only rows created through this HealthSync (ids above the offset)."""
    if not offset():
        return rows
    return [r for r in rows if (r.get("case") or {}).get("patientId", 0) > offset()]
