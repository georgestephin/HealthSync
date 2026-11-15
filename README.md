# HealthSync

HealthSync is a role-based hospital portal for patients, doctors, admins and super admins. Patients book appointments, check in to a live outpatient queue and see ward bed availability. Admins confirm new appointments and manage doctors, users, inventory and bed counts, and see the analytics charts. Doctors run their own queue and complete visits. The super admin oversees everything, including patient records, and can use **View as** on any account.

It is a minor project demo built with **Python, Flask, SQLite and plain HTML, CSS and JavaScript**, and it runs entirely on your own computer.

## Features

- **Landing page** with a live ward directory, quick actions, five departments (Cardiology, Orthopedics, General Medicine, General Surgery and Cardiothoracic Surgery) and their doctors, patient reviews and emergency contact. Each department name opens a public page listing its doctors with their available days and consultation fees.
- **Patients:** register, book, track and cancel appointments, check in to the live queue, view services, doctors and bed availability, and send feedback.
- **Live outpatient queue:** token numbers per doctor, people ahead of you, the token now being served and an estimated wait. Pages refresh themselves automatically, and a board for signed-in users shows token numbers only.
- **Doctors:** follow their own appointments, complete visits, run their own queue and update bed counts.
- **Admins:** confirm patients' appointments (only admins can), and manage doctor profiles (with logins), users, inventory, bed counts, feedback and reports.
- **Super admin:** oversees the platform: appointments (except confirming), the queue, patient records, inventory, users, doctors and reports, plus admin roles and **View as** for any patient, doctor or admin account.
- **Insurance claims (TPA and Ayushman):** patients verify a policy or card, doctors recommend treatment from a confirmed appointment, and an insurance desk approves, queries or rejects the pre-authorization and later settles the claim. The patient follows every step. This part needs the separate **Claims service** (see below).
- **Reports and analytics for admins:** eight charts drawn from live data (appointments per month, by status, by department and per doctor, ward occupancy, today's queue by department, patient ratings and users by role), plus summary tiles and a low-stock list.
- **Form validation** in the browser and on the server, a responsive layout for phones, and clear role-based navigation.

## Technology

| Area | What is used | How it is used |
|---|---|---|
| Language | **Python 3.9+** | All backend logic |
| Web framework | **Flask 3.1** | URL routing, sessions, requests. Built with an app factory (`create_app()`) and seven blueprints |
| Templates | **Jinja2** | Page layouts, template inheritance, macros for form fields, badges and icons, automatic output escaping |
| Security libraries | **Werkzeug**, **itsdangerous** | Password hashing, the development server, signed session cookies |
| Command line | **Click** | The `flask create-user` command |
| Database | **SQLite** via Python's `sqlite3` | Eight tables with foreign keys, UNIQUE constraints, an index and parameterised SQL queries |
| Frontend | **HTML5**, **CSS3**, inline **SVG** | Hand-written responsive styles (Grid, Flexbox, custom properties, media queries), icons, logo and the report charts |
| Browser scripting | **Vanilla JavaScript** | Constraint Validation API for form messages, Fetch API for live queue updates, mobile menu, table filtering, confirm dialogs |
| Fonts | System fonts (Segoe UI, Palatino/Georgia) | Fast loading and offline use |
| Testing | **pytest** with Flask's test client | 50 automated tests with a temporary database per test |
| Tooling | **VS Code**, **venv**, **pip**, **Git** | Editing, F5 debugging, isolated packages, version control |

### Application design

- **Colour theme:** deep blue on the large surfaces (hero, page banners, login panel) with a slight sea-green fade and sea-green accents, a clear blue for buttons and links, cool light-blue backgrounds, and soft pastel colours for the admin charts. Green marks healthy status and red is reserved for emergencies. All colours live in the variables at the top of `static/style.css`.
- **Role-based access control** with a `@login_required(role, ...)` decorator for four roles: patient, doctor, admin and super admin.
- **CSRF protection:** every form carries a per-session token that is checked on each POST.
- **Shared validation:** one set of field definitions drives both the HTML form and the server-side checks.
- **Config-driven pages:** patients, doctors, inventory and beds share one generic list-and-form view.
- **Server-side charts:** `charts.py` turns query results into inline SVG (columns, bars, donuts, stacked bars), so the reports work offline.
- **Atomic token numbering:** each token is assigned in a single SQL statement, and a UNIQUE constraint on (doctor, day, token) keeps numbers unique.
- **Wait estimate:** the doctor's average consultation time (last 20 completed visits, 10 minutes until data exists, kept between 3 and 45) plus the time left for the patient currently in the room. For the person at position *i* in the waiting list, the estimate is the time left for the current patient plus *i* times the average.
- **View as:** the super admin's session remembers the real account, so one click returns to it.

## How it works

1. `app.py` calls `create_app()`, which loads the settings, creates the tables from `schema.sql`, adds demo data on an empty database and registers the blueprints.
2. Each request passes a CSRF check. `@login_required` reads the signed session cookie, loads the user from SQLite and checks the role.
3. The blueprint validates the input, applies the business rules (for example, a booking slot cannot be taken twice) and reads or writes SQLite.
4. Jinja renders the page, with CSS for styling and JavaScript for the interactive parts.
5. Live pages (queue, board) ask the server every few seconds for a fresh fragment and swap it into the page.

## Run it in VS Code (Windows)

1. Open the project folder (the one containing `app.py`) with **File > Open Folder**.
2. Open a terminal with **Ctrl + `** and run:
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```
   If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first.
3. Open **http://127.0.0.1:5000** in your browser.

On macOS or Linux, use `source venv/bin/activate` to activate the environment.

You can also press **F5** and choose **HealthSync: run app** to start the app with the debugger.

The database and demo data are created automatically in `instance/healthsync.db` on the first run. To reset everything, stop the server, delete that file and start the app again.

## Demo accounts

These are created on the first run and are also listed on the login page, where clicking a row fills the form.

### Patients

| Name | Email | Password |
|---|---|---|
| Rahul Verma | patient@healthsync.local | Patient@123 |
| Sunita Devi | sunita@healthsync.local | Patient@123 |
| Aarav Gupta | aarav@healthsync.local | Patient@123 |
| Neha Kapoor | neha@healthsync.local | Patient@123 |
| Imran Sheikh | imran@healthsync.local | Patient@123 |
| Lakshmi Narayanan | lakshmi@healthsync.local | Patient@123 |
| Karan Malhotra | karan@healthsync.local | Patient@123 |
| Divya Rao | divya@healthsync.local | Patient@123 |
| Suresh Reddy | suresh@healthsync.local | Patient@123 |
| Meenakshi Iyer | meenakshi@healthsync.local | Patient@123 |

### Doctors (five departments, two doctors each)

| Department | Name | Email | Password |
|---|---|---|---|
| Cardiology | Dr. Anita Sharma | doctor@healthsync.local | Doctor@123 |
| Cardiology | Dr. Rohan Mehta | rohan@healthsync.local | Doctor@123 |
| Orthopedics | Dr. Vikram Rao | vikram@healthsync.local | Doctor@123 |
| Orthopedics | Dr. Kavita Nair | kavita@healthsync.local | Doctor@123 |
| General Medicine | Dr. Sameer Khan | sameer@healthsync.local | Doctor@123 |
| General Medicine | Dr. Priya Menon | priya@healthsync.local | Doctor@123 |
| General Surgery | Dr. Rajiv Malhotra | rajiv@healthsync.local | Doctor@123 |
| General Surgery | Dr. Farah Siddiqui | farah@healthsync.local | Doctor@123 |
| Cardiothoracic Surgery | Dr. Harish Venkatesh | harish@healthsync.local | Doctor@123 |
| Cardiothoracic Surgery | Dr. Ananya Kulkarni | ananya@healthsync.local | Doctor@123 |

### Insurance desks

| Desk | Email | Password |
|---|---|---|
| TPA desk (private insurance) | tpadesk@healthsync.local | Desk@123 |
| Ayushman (PM-JAY) desk | pmjaydesk@healthsync.local | Desk@123 |

### Admin and super admin

| Role | Email | Password |
|---|---|---|
| Admin | admin@healthsync.local | Admin@123 |
| Super admin | superadmin@healthsync.local | Super@123 |

Today's appointments and queues are seeded in every department, so each doctor's queue console and the live board have something to show. `patient@healthsync.local` and `divya@healthsync.local` have a confirmed appointment today and have not checked in yet, so they can try **Check in**. New visitors can also register as patients at `/register`.

## What each role can do

| Feature | Patient | Doctor | Admin | Super admin |
|---|:-:|:-:|:-:|:-:|
| View services, departments with their doctors, and bed availability | yes | yes | yes | yes |
| Book, track and cancel own appointments | yes | | | |
| Check in and follow own place in the queue | yes | | | |
| Send feedback | yes | | | |
| **Confirm** a patient's appointment | | | yes | |
| Complete visits | | yes (own) | | yes |
| Cancel appointments | yes (own) | yes (own) | yes | yes |
| Run the queue (call next, complete, no-show) and see the queue board | | yes (own) | | yes |
| Add walk-in patients to a queue | | | | yes |
| Add and edit patient records | | | | yes |
| Update inventory | | | yes | yes |
| Verify own coverage and follow own treatments and claims | yes | | | |
| Recommend treatment, answer desk queries, discharge (own patients) | | yes | | |
| Update bed counts | | yes | yes | yes |
| Add, edit and delete doctor profiles (with login) | | | yes | yes |
| View all feedback | | yes | yes | yes |
| Reports and analytics (charts, including ward occupancy) | | | yes | yes |
| Manage users (patient and doctor roles) | | | yes | yes |
| Assign admin and super admin roles | | | | yes |
| **View as** any patient, doctor or admin account | | | | yes |

The two insurance desks (TPA and Ayushman) have their own accounts and only see the claims screens. Only admins confirm appointments. Once confirmed, the patient can check in on the day, and the doctor completes the visit from **Appointments** or by completing the consultation in the **Queue**. Each role's menu and dashboard show only its own pages, and appointment booking belongs to patients.

### Adding a doctor
Admins and super admins open **Doctors** and fill in **Add a doctor**. Entering a login email and temporary password creates the doctor's login in the same step. That doctor then signs in and sees their own appointments and queue. A profile without a login can be linked to an existing doctor login later with **Edit**.

### View as (super admin)
On the **Users** page, **View as** shows the app exactly as that person sees it. A banner shows who you are viewing, and **Return to super admin** brings you back.

## The live queue

- A patient with an appointment **confirmed by an admin** checks in on the day under **My queue** and receives a token number (per doctor, per day).
- Patients are served first come, first served. The patient sees how many people are ahead, the token now being served and an estimated wait.
- The estimate improves as staff press **Call next** and **Complete**, because it uses the doctor's real consultation times.
- Doctors and the super admin use the **Queue** console to call the next patient, complete a consultation or mark a no-show. Only the super admin can add walk-in patients.
- The **Live queue** board, available to patients, doctors and the super admin after signing in, shows token numbers only, which keeps patient names private.

## Project structure

```
healthsync/                     <- open this folder in VS Code
├── app.py                      entry point (creates the app, runs the dev server)
├── requirements.txt            Flask
├── requirements-dev.txt        pytest
├── .vscode/                    launch, test and editor settings
├── tests/
│   ├── conftest.py             test app and a small browser helper
│   ├── test_flows.py           public pages, registration, booking, permissions, CSRF
│   ├── test_queue.py           check-in, queue order, completion, permissions
│   ├── test_roles.py           booking rules, adding doctors, View as
│   ├── test_demo.py            departments, demo logins, live queues, report charts
│   ├── test_claims.py          full TPA and Ayushman journeys, permissions, errors
│   └── fake_claims.py          in-memory stand-in for the Claims service
└── healthsync/                 the application package
    ├── __init__.py             create_app(): config, database, blueprints
    ├── config.py               settings (SECRET_KEY, booking window, queue default, seeding)
    ├── constants.py            roles, specialties, time slots, services list
    ├── db.py                   SQLite connection and query helpers
    ├── schema.sql              table definitions
    ├── demo_data.py            demo doctors, patients and accounts (login page and seed)
    ├── seed.py                 demo users, appointments, queues, reviews and sample data
    ├── charts.py               server-side SVG charts for the reports page
    ├── queue_logic.py          tokens, positions and wait estimates
    ├── claims_client.py        talks to the separate Claims service
    ├── live.py                 pages that refresh themselves
    ├── security.py             current_user() and @login_required(role...)
    ├── validation.py           form field specs and server-side validation
    ├── services.py             shared helpers (patient and doctor lookup)
    ├── hooks.py                CSRF check, template context, error pages
    ├── cli.py                  flask create-user command
    ├── blueprints/
    │   ├── public.py           landing page, services
    │   ├── auth.py             login, register, logout
    │   ├── dashboard.py        role-based dashboards
    │   ├── appointments.py     booking, tracking, status changes
    │   ├── queueing.py         check-in, live queue board, staff console
    │   ├── claims.py           insurance claims screens (patient, doctor, desks)
    │   ├── records.py          patients, doctors, inventory, beds
    │   ├── feedback.py         patient feedback
    │   └── admin.py            users and roles, View as, reports
    ├── templates/              Jinja pages and live fragments
    └── static/                 style.css, app.js
```

To add a page, create a blueprint in `blueprints/`, register it in `__init__.py` and add a template. To add another list-and-form page (for example *Wards* or *Lab tests*), add an entry to `CONFIG` in `blueprints/records.py`.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

You should see `50 passed`. In VS Code you can also use the **Testing** panel.

## Insurance claims (TPA and Ayushman)

The claims logic lives in a separate service (`claims_service`, NestJS, port 3001, its own database). HealthSync shows the screens and passes each action to it; the service does the calculations. Nothing in the claims service or its database structure is changed by HealthSync.

**Run both apps at the same time**

1. In the claims service folder: `npm run start:dev` (wait for "Claims service running on http://localhost:3001").
2. In the HealthSync folder: `python app.py`.

If the claims service is not running, the rest of HealthSync works normally and the claims screens show "The claims service is not reachable".

**Try the whole journey** (demo values come from the claims service seed data)

1. Patient `patient@healthsync.local`: **Coverage**, choose Private insurance, enter `TPA-1001`, Verify. (For Ayushman use `PMJAY-1001`.)
2. Doctor `doctor@healthsync.local`: **Appointments**, on Rahul Verma's confirmed appointment click **Recommend treatment**, enter a diagnosis and estimated cost (Ayushman: pick a package such as `GS-001`).
3. TPA desk `tpadesk@healthsync.local` (Ayushman: `pmjaydesk@healthsync.local`): **Pre-authorizations**, then **Approve**, **Query** or **Reject**.
4. Doctor: **Treatment cases**, answer a query if there is one, then **Discharge** and enter the final bill. The split of who pays what updates as you type.
5. Desk: **Claims**, then **Settle** (only possible once the pre-authorization is approved) or **Reject**.
6. Patient: **Treatments** shows every status, and **Coverage** shows the new balance.

Tick **Emergency** when recommending to admit the patient straight away; the desk must then decide within 24 hours.

**How the two systems connect:** HealthSync sends the claims service three headers (`user_id`, `role`, `user_name`) for the logged-in person. The service has no passwords or tokens, so only HealthSync should be able to reach it. Patient and doctor ids are shifted by `CLAIMS_ID_OFFSET`, and the desk screens only list claims created through this HealthSync.

## Settings

| Setting | How to set it | Purpose |
|---|---|---|
| `SECRET_KEY` | `$env:SECRET_KEY="long-random-text"` | Signs session cookies |
| `PORT` | `$env:PORT=8000` | Runs the app on another port |
| `SEED_DEMO_DATA` | `$env:SEED_DEMO_DATA="0"` | Starts with an empty database |
| `CLAIMS_API_URL` | `$env:CLAIMS_API_URL="http://localhost:3001/api/v1"` | Where the Claims service runs (this is the default) |
| `CLAIMS_ID_OFFSET` | `$env:CLAIMS_ID_OFFSET="100000"` | Added to patient, doctor and appointment ids sent to the Claims service, so they never clash with another system using the same claims database (default 100000) |
| `BOOKING_WINDOW_DAYS`, `QUEUE_DEFAULT_MINUTES` | `healthsync/config.py` | Booking range and the default consultation length |

Create your own first super admin with:
```powershell
flask --app app create-user you@example.com "Your Name" --role superadmin
```

HealthSync is built as a minor project demo and ships with sample data.
