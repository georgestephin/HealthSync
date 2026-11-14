STAFF = ("doctor", "admin", "superadmin")
ADMINS = ("admin", "superadmin")
SUPERADMIN = ("superadmin",)
CARE = ("doctor", "superadmin")   # roles that handle appointments and the queue
HMS_ROLES = ("patient", "doctor", "admin", "superadmin")
DESKS = ("tpa_desk", "pmjay_desk")                       # insurance desk accounts (claims screens only)
ROLES = HMS_ROLES + DESKS
CLAIMS_ROLE = {"patient": "PATIENT", "doctor": "DOCTOR", "tpa_desk": "TPA_DESK", "pmjay_desk": "PMJAY_DESK"}   # HealthSync role -> Claims service role
DESK_TITLES = {"tpa_desk": "TPA Desk", "pmjay_desk": "Ayushman (PM-JAY) Desk"}

SPECIALTIES = ["General Medicine", "Cardiology", "Orthopedics", "Pediatrics", "General Surgery", "Cardiothoracic Surgery",
               "Gynecology", "Neurology", "Dermatology", "ENT"]
SLOTS = [f"{h:02d}:{m}" for h in range(9, 17) for m in ("00", "30")]
DEPT_COLORS = {"General Medicine": "#2e9b7f", "Cardiology": "#c0505e", "Orthopedics": "#3b82c4", "Pediatrics": "#d68a00", "General Surgery": "#0e8a8a",
               "Cardiothoracic Surgery": "#274b8f", "Gynecology": "#d9776b", "Neurology": "#4a78b5", "Dermatology": "#b8742c", "ENT": "#2b8fb3"}
DEPT_INFO = {
    "Cardiology": "Diagnosis and long-term care for heart and blood-pressure conditions.",
    "Orthopedics": "Treatment for bones, joints, muscles and sports injuries.",
    "General Medicine": "First-line care for everyday illness, chronic conditions and health checks.",
    "General Surgery": "Planned and urgent operations, including gallbladder, hernia and abdominal surgery.",
    "Cardiothoracic Surgery": "Major operations on the heart, lungs and chest, such as bypass and valve surgery.",
    "Pediatrics": "Healthcare for infants, children and teenagers.",
    "Gynecology": "Women's health, pregnancy care and reproductive medicine.",
    "Neurology": "Care for the brain, spine and nervous system.",
    "Dermatology": "Skin, hair and nail conditions.",
    "ENT": "Ear, nose and throat care.",
}
GENDERS = ["Female", "Male", "Other"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
PHONE = dict(pattern=r"[0-9]{10}", hint="Enter a 10-digit phone number.")

SERVICES = [
    ("Emergency & Trauma", "24/7 emergency care with a rapid-response team and ambulance support."),
    ("Outpatient Consultations", "Same-week appointments across all major specialties."),
    ("Inpatient Care", "General, ICU, maternity and pediatric wards with round-the-clock nursing."),
    ("Diagnostics & Laboratory", "Blood tests, X-ray, ultrasound and ECG with reports within a day."),
    ("Pharmacy", "In-house pharmacy open 24 hours, stocked against live inventory."),
    ("Maternity & Newborn Care", "Antenatal checkups, delivery suites and newborn monitoring."),
    ("Cardiac Care", "ECG, echo and stress testing with cardiology follow-up."),
    ("Pediatrics & Vaccination", "Child health checkups and the full immunization schedule."),
]
