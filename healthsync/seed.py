"""Demo data created on first run when the database is empty."""
import random
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash
from .constants import SLOTS
from .db import get_db
from .demo_data import ADMIN, DESK_ACCOUNTS, DESK_PASSWORD, DOCTOR_PASSWORD, DOCTORS, PATIENT_PASSWORD, PATIENTS, SUPER

REASONS = ["Routine checkup", "Follow-up visit", "Fever", "Back pain", "Skin rash", "Headache", "Blood test review", "Vaccination"]

# Today's schedule: (patient, doctor, slot, reason, appointment status, queue entry)
# queue entry = (token, status, minutes since check-in, minutes since started, minutes since finished) or None (not checked in yet).
# Doctor 1's queue is kept at tokens 1 (done) and 2 (in consultation) so patient@ checks in as token 3.
TODAY = [
    (6, 1, "09:30", "Cardiac follow-up", "Completed", (1, "Done", 70, 62, 50)),
    (5, 1, "10:00", "Chest discomfort", "Confirmed", (2, "In consultation", 40, 6, None)),
    (1, 1, "10:30", "Blood pressure check", "Confirmed", None),
    (7, 2, "10:00", "Knee pain", "Confirmed", (1, "In consultation", 30, 12, None)),
    (4, 2, "10:30", "Ankle sprain", "Confirmed", (2, "Waiting", 15, None, None)),
    (3, 3, "10:00", "Asthma review", "Confirmed", (1, "In consultation", 25, 4, None)),
    (2, 6, "10:00", "Diabetes follow-up", "Confirmed", (1, "In consultation", 22, 9, None)),
    (8, 6, "11:00", "Fever and fatigue", "Confirmed", None),
    (9, 7, "10:00", "Gallbladder consultation", "Confirmed", (1, "In consultation", 35, 14, None)),
    (10, 9, "10:30", "Heart valve assessment", "Confirmed", (1, "Waiting", 20, None, None)),
]

REVIEWS = [  # (patient, rating, message, days ago); the newest good ones appear on the landing page
    (1, 5, "Quick appointment booking and a very helpful doctor.", 60), (2, 4, "Clean wards. Waiting time at the pharmacy could be shorter.", 45),
    (4, 5, "The doctor explained everything patiently and clearly.", 35), (5, 3, "Good treatment, but the waiting area was crowded.", 30),
    (6, 5, "Staff were kind and the process was well organised.", 25), (3, 5, "Loved being able to check bed availability before travelling.", 20),
    (8, 2, "My appointment started late and nobody told me why.", 12), (7, 4, "Booking online saved me a long trip to the hospital.", 9),
    (9, 5, "Excellent surgical consultation, everything was explained clearly.", 6), (10, 4, "Easy to follow my place in the queue from my phone.", 2),
]


def seed_demo_data():
    db = get_db()

    def ins(sql, args):
        return db.execute(sql, args).lastrowid

    # Demo accounts of the same role share one password hash, which keeps seeding fast.
    h_super, h_admin = generate_password_hash(SUPER[2]), generate_password_hash(ADMIN[2])
    h_doc, h_pat = generate_password_hash(DOCTOR_PASSWORD), generate_password_hash(PATIENT_PASSWORD)
    user = lambda name, email, pw, role: ins("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", (name, email, pw, role))

    user(SUPER[0], SUPER[1], h_super, "superadmin")
    user(ADMIN[0], ADMIN[1], h_admin, "admin")
    for d in DOCTORS:
        uid = user(d["name"], d["email"], h_doc, "doctor")
        ins("INSERT INTO doctors(user_id,name,specialty,phone,fee,available_days) VALUES(?,?,?,?,?,?)", (uid, d["name"], d["specialty"], d["phone"], d["fee"], d["days"]))
    patient_users = []
    for p in PATIENTS:
        uid = user(p["name"], p["email"], h_pat, "patient")
        patient_users.append(uid)
        ins("INSERT INTO patients(user_id,name,age,gender,phone,blood_group,address,history) VALUES(?,?,?,?,?,?,?,?)",
            (uid, p["name"], p["age"], p["gender"], p["phone"], p["blood"], p["address"], p["history"]))

    h_desk = generate_password_hash(DESK_PASSWORD)
    for d in DESK_ACCOUNTS:                                  # appended last, so every other user keeps its id
        user(d["name"], d["email"], h_desk, d["role"])

    today, now, used = date.today(), datetime.now().replace(microsecond=0), set()

    def appt(patient, doctor, day, slot, reason, status):
        used.add((doctor, day, slot))
        return ins("INSERT INTO appointments(patient_id,doctor_id,date,time,reason,status) VALUES(?,?,?,?,?,?)", (patient, doctor, day, slot, reason, status))

    iso = lambda offset: (today + timedelta(days=offset)).isoformat()
    ago = lambda minutes: (now - timedelta(minutes=minutes)).isoformat()
    # The first four appointments keep ids 1-4.
    for pid, did, off, slot, reason, status in [(1, 1, 2, "10:00", "Blood pressure review", "Confirmed"), (2, 3, 1, "11:30", "Routine checkup", "Pending"),
                                                (3, 3, 3, "09:30", "Cough and wheezing", "Pending"), (1, 6, -10, "14:00", "Fever", "Completed")]:
        appt(pid, did, iso(off), slot, reason, status)
    for pid, did, slot, reason, status, queue in TODAY:
        aid = appt(pid, did, iso(0), slot, reason, status)
        if queue:
            token, qstatus, checked, started, finished = queue
            ins("INSERT INTO queue_entries(patient_id,doctor_id,appointment_id,day,token,status,checked_in,started,finished) VALUES(?,?,?,?,?,?,?,?,?)",
                (pid, did, aid, iso(0), token, qstatus, ago(checked), ago(started) if started else None, ago(finished) if finished else None))

    # Past and upcoming appointments give the admin charts something to show.
    rng = random.Random(42)
    for _ in range(130):
        did, slot, off = rng.randint(1, len(DOCTORS)), rng.choice(SLOTS), -rng.randint(8, 165)
        if (did, iso(off), slot) not in used:
            appt(rng.randint(1, len(PATIENTS)), did, iso(off), slot, rng.choice(REASONS), rng.choice(["Completed"] * 8 + ["Cancelled"]))
    for _ in range(14):
        did, slot, off = rng.randint(1, len(DOCTORS)), rng.choice(SLOTS), rng.choice([1, 2, 3, 4, 7])
        if (did, iso(off), slot) not in used:
            appt(rng.randint(1, len(PATIENTS)), did, iso(off), slot, rng.choice(REASONS), rng.choice(["Pending", "Confirmed"]))

    for ward, total, occupied in [("General Ward", 40, 27), ("ICU", 10, 9), ("Maternity", 12, 5), ("Pediatrics", 15, 6), ("Emergency", 8, 3), ("Surgical Ward", 20, 14)]:
        ins("INSERT INTO beds(ward,total,occupied) VALUES(?,?,?)", (ward, total, occupied))
    for item, cat, qty, unit, reorder in [
        ("Paracetamol 500mg", "Medicine", 240, "strips", 50), ("Amoxicillin 250mg", "Medicine", 125, "strips", 40),
        ("Insulin (regular)", "Medicine", 18, "vials", 20), ("Surgical gloves", "Supplies", 600, "pairs", 200),
        ("Syringes 5ml", "Supplies", 90, "boxes", 100), ("IV fluids (saline)", "Supplies", 60, "bags", 30),
        ("Oxygen cylinders", "Equipment", 14, "units", 10), ("Surgical sutures", "Supplies", 150, "packs", 60),
        ("Anaesthetic (propofol)", "Medicine", 35, "vials", 40), ("Sterile surgical drapes", "Supplies", 220, "packs", 80)]:
        ins("INSERT INTO inventory(item,category,qty,unit,reorder_level) VALUES(?,?,?,?,?)", (item, cat, qty, unit, reorder))
    for pid, rating, message, days in REVIEWS:
        ins("INSERT INTO feedback(user_id,rating,message,created) VALUES(?,?,?,?)", (patient_users[pid - 1], rating, message, (now - timedelta(days=days)).isoformat(sep=" ")))
    db.commit()
