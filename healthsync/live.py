"""Pages that refresh themselves: the full page, or just the changing fragment when ?partial=1."""
from datetime import datetime
from flask import make_response, render_template, request


def page(template, **ctx):
    partial = bool(request.args.get("partial"))
    ctx["updated"] = datetime.now().strftime("%H:%M:%S")
    resp = make_response(render_template(ctx.pop("fragment") if partial else template, **ctx))
    if partial:
        resp.headers["X-Live"] = "1"
        resp.headers["Cache-Control"] = "no-store"
    return resp
