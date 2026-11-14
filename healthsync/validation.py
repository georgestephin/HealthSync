"""Form field specs: preparing them for templates and validating submitted values."""
import re
from datetime import date


def opts(field):
    options = field.get("options", [])
    options = options() if callable(options) else options
    return [(x, x) if isinstance(x, str) else tuple(x) for x in options]


def prep(fields):
    """Resolve defaults and select options so templates can render the fields."""
    out = []
    for f in fields:
        t = f.get("type", "text")
        d = dict(f, type=t, required=f.get("required", True), opts=opts(f) if t == "select" else [])
        if t == "number":
            d.update(min=f.get("min", 0), max=f.get("max", 10**6))
        out.append(d)
    return out


def pw_error(password):
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Use at least 8 characters with a letter and a number."


def validate(fields, form):
    """Return (values, errors) for a submitted form according to the field specs."""
    vals, errs = {}, {}
    for f in fields:
        name, t, label = f["name"], f.get("type", "text"), f["label"]
        raw = (form.get(name) or "").strip()
        if not raw:
            if f.get("required", True):
                errs[name] = f"{label} is required."
            vals[name] = None if t in ("number", "select") else ""
            continue
        vals[name] = raw
        if t == "number":
            try:
                v = int(raw)
            except ValueError:
                errs[name] = "Enter a whole number."
                continue
            lo, hi = f.get("min", 0), f.get("max", 10**6)
            vals[name] = v
            if not lo <= v <= hi:
                errs[name] = f"{label} must be between {lo} and {hi}."
        elif t == "select" and raw not in [str(k) for k, _ in opts(f)]:
            errs[name] = "Choose a valid option."
        elif t == "date":
            try:
                date.fromisoformat(raw)
            except ValueError:
                errs[name] = "Enter a valid date."
        elif t == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw):
            errs[name] = "Enter a valid email address."
        elif f.get("pattern") and not re.fullmatch(f["pattern"], raw):
            errs[name] = f.get("hint", "Invalid format.")
        elif len(raw) < f.get("minlength", 0):
            errs[name] = f"{label} must be at least {f['minlength']} characters."
        elif len(raw) > f.get("maxlength", 500):
            errs[name] = f"{label} must be at most {f.get('maxlength', 500)} characters."
    return vals, errs
