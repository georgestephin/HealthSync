from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from ..constants import HMS_ROLES, STAFF
from ..db import q, run
from ..security import current_user, login_required
from ..validation import prep, validate

bp = Blueprint("feedback", __name__)

RATINGS = [(5, "5 - Excellent"), (4, "4 - Good"), (3, "3 - Okay"), (2, "2 - Poor"), (1, "1 - Very poor")]


@bp.route("/feedback", methods=["GET", "POST"])
@login_required(*HMS_ROLES)
def index():
    user = current_user()
    staff = user["role"] in STAFF
    fields = [dict(name="rating", label="Rating", type="select", options=RATINGS),
              dict(name="message", label="Your feedback", type="textarea", minlength=10)]
    vals, errs = {}, {}
    if request.method == "POST":
        if staff:
            abort(403)
        vals, errs = validate(fields, request.form)
        if not errs:
            run("INSERT INTO feedback(user_id,rating,message) VALUES(?,?,?)", (user["id"], vals["rating"], vals["message"]))
            flash("Thank you. Your feedback has been sent to the HealthSync team.", "ok")
            return redirect(url_for("feedback.index"))
    sql = "SELECT f.rating,f.message,substr(f.created,1,10) AS date,COALESCE(u.name,'Anonymous') AS who FROM feedback f LEFT JOIN users u ON u.id=f.user_id"
    found = q(sql + " ORDER BY f.id DESC") if staff else q(sql + " WHERE f.user_id=? ORDER BY f.id DESC", (user["id"],))
    rows = [dict(r, rating=f'{r["rating"]}/5', acts=[]) for r in found]
    page = dict(title="Feedback", intro="All patient feedback." if staff else "Tell us how your visit went. We read every message.",
                show_form=not staff, form_title="Send feedback", submit="Send feedback", fields=prep(fields), rows=rows, badges=set(),
                empty="No feedback yet.", cols=[("Date", "date")] + ([("From", "who")] if staff else []) + [("Rating", "rating"), ("Message", "message")])
    return render_template("crud.html", c=page, vals=vals, errs=errs, edit_id=None)
