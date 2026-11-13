# TDRIVE Driving School Management App

Co-branded for **Viva Toyota** and **TDRIVE**. Flask application with separate student, staff and admin roles.

## Included
- Student self-registration and login
- Separate staff and administrator login (same login page; permissions are role-based)
- Student practical and simulator bookings
- Booking conflict checks and cancellation
- Admin overview, booking list, staff/admin account creation and account activation
- Five driving theory quiz categories and saved quiz scores
- SQLite locally; PostgreSQL through `DATABASE_URL` in cloud hosting
- Render deployment blueprint

## Local run (Windows / macOS / Linux)
1. Install Python 3.11 or 3.12.
2. Extract the ZIP and open a terminal in the project folder.
3. Create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install packages: `pip install -r requirements.txt`
5. Initialize database: `flask --app app init-db`
6. Create your admin login: `flask --app app create-admin`
7. Run: `flask --app app run --host=0.0.0.0 --port=5000`
8. Open `http://127.0.0.1:5000`. Admin login is at `/login`; `/admin` redirects to the admin dashboard after login.

## Deploy on Render
1. Create a GitHub account if needed and create a **private** repository.
2. Upload the extracted project files to the repository (do not upload `.env`, database files, or secrets).
3. In Render, choose **New + → Blueprint**, connect the repository, and let Render read `render.yaml`.
4. Review the web service and PostgreSQL database, then deploy.
5. After deployment, open the service Shell (or use a one-off command) and run:
   `flask --app app create-admin`
   Enter your admin name, email and a strong unique password when prompted.
6. Open the public service URL and sign in at `/login`; admin dashboard is `/admin`.

## Important booking rules currently configured
- Practical: Monday–Thursday and Saturday; Friday and Sunday off.
- Practical times: 06:30, 07:30, 08:30, 10:00, 11:00, 12:00, 14:00, 15:00.
- Simulator: Monday–Saturday; Sunday off.
- Simulator times: 09:00, 10:00, 11:00, 12:00, 14:00, 15:00, 16:00, 17:00.
- A time slot can have only one confirmed booking across the app.
- Students can cancel their own bookings. Admin can cancel any booking.

## Before real-world launch
- Confirm class capacity and whether each slot can take more than one student.
- Add instructor assignment, SMS/email notifications, course enrolment and fee collection only when requirements are finalized.
- Review local traffic-rule quiz content with your driving-school trainer before using it for formal assessment.
- Use HTTPS, a strong secret key and a managed database. Keep the GitHub repository private.
- This starter has role-based access but is not a substitute for a full security audit. Add CSRF protection, rate limiting, audit logs and tested backups before handling sensitive student data at scale.
