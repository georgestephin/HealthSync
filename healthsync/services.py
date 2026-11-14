"""Small domain helpers shared by several blueprints."""
from .db import q, run


def my_patient(user):
    """Patient id for a user. Patient-role users get a record created on demand."""
    row = q("SELECT id FROM patients WHERE user_id=?", (user["id"],), one=True)
    if row:
        return row["id"]
    if user["role"] == "patient":
        return run("INSERT INTO patients(user_id,name) VALUES(?,?)", (user["id"], user["name"]))
    return None


def my_doctor(user):
    """Doctor profile row for a user with the doctor role (or None)."""
    if user["role"] != "doctor":
        return None
    return q("SELECT id FROM doctors WHERE user_id=?", (user["id"],), one=True)
