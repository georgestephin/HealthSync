"""App-wide request hooks: CSRF protection, template context, error pages."""
import secrets
from flask import abort, render_template, request, session
from .constants import ADMINS, CARE, DESKS
from .security import current_user

ERRORS = {
    400: "That request could not be verified. Go back, refresh the page and try again.",
    403: "Your role does not have access to this page.",
    404: "We could not find that page.",
}


def init_app(app):
    @app.before_request
    def csrf_guard():
        session.setdefault("csrf", secrets.token_hex(16))
        if request.method == "POST" and request.form.get("_csrf") != session["csrf"]:
            abort(400)

    @app.context_processor
    def inject():
        user, menu = current_user(), []
        if user:
            role = user["role"]
            menu = [("Dashboard", "dashboard.index")]
            if role in DESKS:
                menu += [("Pre-authorizations", "claims.desk_preauths"), ("Claims", "claims.desk_claims")]
            else:
                menu.append(("Appointments", "appointments.index"))
                if role == "patient" or role in CARE:
                    menu.append(("My queue" if role == "patient" else "Queue", "queue.index"))
                if role == "patient":
                    menu += [("Coverage", "claims.coverage"), ("Treatments", "claims.treatments")]
                if role == "doctor":
                    menu.append(("Treatment cases", "claims.cases"))
                if role == "superadmin":
                    menu.append(("Patients", "records.patients"))
                if role in ADMINS:
                    menu += [("Inventory", "records.inventory"), ("Reports", "admin.reports"), ("Users", "admin.users")]
                menu.append(("Feedback", "feedback.index"))
        return dict(user=user, menu=menu, viewing_as=bool(session.get("impersonator")), csrf_token=lambda: session.get("csrf", ""))

    def show_error(e):
        return render_template("error.html", code=e.code, msg=ERRORS[e.code]), e.code

    for code in ERRORS:
        app.register_error_handler(code, show_error)
