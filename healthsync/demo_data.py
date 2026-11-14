"""Demo accounts and sample records.
One source of truth: seed.py creates these rows and the login page lists them."""

SUPER = ("Super Admin", "superadmin@healthsync.local", "Super@123")
ADMIN = ("HealthSync Admin", "admin@healthsync.local", "Admin@123")
DOCTOR_PASSWORD = "Doctor@123"
DESK_PASSWORD = "Desk@123"
DESK_ACCOUNTS = [dict(name="TPA Desk", email="tpadesk@healthsync.local", role="tpa_desk"),
                 dict(name="Ayushman (PM-JAY) Desk", email="pmjaydesk@healthsync.local", role="pmjay_desk")]
PATIENT_PASSWORD = "Patient@123"

# Order matters: tests and the seed refer to doctors and patients by position (doctor 1 is Dr. Anita Sharma, patient 1 is Rahul Verma).
DOCTORS = [
    dict(name="Dr. Anita Sharma", email="doctor@healthsync.local", specialty="Cardiology", phone="9810000001", fee=800, days="Mon, Wed, Fri"),
    dict(name="Dr. Vikram Rao", email="vikram@healthsync.local", specialty="Orthopedics", phone="9810000002", fee=700, days="Tue, Thu, Sat"),
    dict(name="Dr. Sameer Khan", email="sameer@healthsync.local", specialty="General Medicine", phone="9810000003", fee=400, days="Mon to Sat"),
    dict(name="Dr. Rohan Mehta", email="rohan@healthsync.local", specialty="Cardiology", phone="9810000004", fee=900, days="Tue, Thu"),
    dict(name="Dr. Kavita Nair", email="kavita@healthsync.local", specialty="Orthopedics", phone="9810000005", fee=750, days="Mon, Wed, Sat"),
    dict(name="Dr. Priya Menon", email="priya@healthsync.local", specialty="General Medicine", phone="9810000006", fee=450, days="Mon to Fri"),
    dict(name="Dr. Rajiv Malhotra", email="rajiv@healthsync.local", specialty="General Surgery", phone="9810000007", fee=1200, days="Mon, Wed, Fri"),
    dict(name="Dr. Farah Siddiqui", email="farah@healthsync.local", specialty="General Surgery", phone="9810000008", fee=1300, days="Tue, Thu, Sat"),
    dict(name="Dr. Harish Venkatesh", email="harish@healthsync.local", specialty="Cardiothoracic Surgery", phone="9810000009", fee=1800, days="Mon, Thu"),
    dict(name="Dr. Ananya Kulkarni", email="ananya@healthsync.local", specialty="Cardiothoracic Surgery", phone="9810000010", fee=1900, days="Tue, Fri"),
]

PATIENTS = [
    dict(name="Rahul Verma", email="patient@healthsync.local", age=34, gender="Male", phone="9820000001", blood="B+", address="Karol Bagh, Delhi", history="Mild hypertension"),
    dict(name="Sunita Devi", email="sunita@healthsync.local", age=58, gender="Female", phone="9820000002", blood="O+", address="Rohini, Delhi", history="Type 2 diabetes"),
    dict(name="Aarav Gupta", email="aarav@healthsync.local", age=7, gender="Male", phone="9820000003", blood="A+", address="Dwarka, Delhi", history="Seasonal asthma"),
    dict(name="Neha Kapoor", email="neha@healthsync.local", age=29, gender="Female", phone="9820000004", blood="AB+", address="Saket, Delhi", history="Ankle ligament injury"),
    dict(name="Imran Sheikh", email="imran@healthsync.local", age=45, gender="Male", phone="9820000005", blood="O-", address="Okhla, Delhi", history="High cholesterol"),
    dict(name="Lakshmi Narayanan", email="lakshmi@healthsync.local", age=63, gender="Female", phone="9820000006", blood="B-", address="Janakpuri, Delhi", history="Atrial fibrillation"),
    dict(name="Karan Malhotra", email="karan@healthsync.local", age=38, gender="Male", phone="9820000007", blood="A-", address="Vasant Kunj, Delhi", history="Old knee injury"),
    dict(name="Divya Rao", email="divya@healthsync.local", age=31, gender="Female", phone="9820000008", blood="B+", address="Pitampura, Delhi", history="Recurring fatigue"),
    dict(name="Suresh Reddy", email="suresh@healthsync.local", age=52, gender="Male", phone="9820000009", blood="O+", address="Lajpat Nagar, Delhi", history="Gallstones"),
    dict(name="Meenakshi Iyer", email="meenakshi@healthsync.local", age=61, gender="Female", phone="9820000010", blood="AB-", address="Mayur Vihar, Delhi", history="Heart valve disease"),
]


def demo_groups():
    """Account groups shown on the login page, in the order: patients, doctors, admin and super admin."""
    order = list(dict.fromkeys(d["specialty"] for d in DOCTORS))   # departments in order of first appearance
    return [
        dict(title="Patients", rows=[dict(name=p["name"], note=f'{p["age"]} yrs', email=p["email"], password=PATIENT_PASSWORD) for p in PATIENTS]),
        dict(title="Doctors", rows=[dict(name=d["name"], dept=d["specialty"], email=d["email"], password=DOCTOR_PASSWORD)
                                    for d in sorted(DOCTORS, key=lambda d: order.index(d["specialty"]))]),
        dict(title="Insurance desks", rows=[dict(name=d["name"], note=d["role"].replace("_", " "), email=d["email"], password=DESK_PASSWORD) for d in DESK_ACCOUNTS]),
        dict(title="Admin and super admin", rows=[dict(name=ADMIN[0], note="admin", email=ADMIN[1], password=ADMIN[2]),
                                                  dict(name=SUPER[0], note="super admin", email=SUPER[1], password=SUPER[2])]),
    ]
