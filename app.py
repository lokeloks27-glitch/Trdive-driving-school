import os
from datetime import date, datetime, timedelta
from functools import wraps

import click
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-only-change-this-before-deploying")
database_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI") or "sqlite:///tdrive.db"
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # admin, staff, student
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship("Booking", backref="student", lazy=True, foreign_keys="Booking.student_id")
    quiz_scores = db.relationship("QuizScore", backref="student", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)
    class_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuizScore(db.Model):
    __tablename__ = "quiz_scores"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)


PRACTICAL_SLOTS = ["06:30", "07:30", "08:30", "10:00", "11:00", "12:00", "14:00", "15:00"]
SIMULATOR_SLOTS = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]
# Practical: Monday–Thursday and Saturday (Friday/Sunday off).
PRACTICAL_DAYS = {0, 1, 2, 3, 5}
# Simulator: Monday–Saturday (Sunday off).
SIMULATOR_DAYS = {0, 1, 2, 3, 4, 5}

QUIZ_DATA = {
    "road_signs": {
        "name": "Road Sign Boards",
        "questions": [
            ("A red octagonal traffic sign means:", ["Stop", "Give way", "No parking", "One way"], 0),
            ("An inverted triangle sign generally means:", ["No entry", "Give way", "School ahead", "Speed limit"], 1),
            ("A blue circular sign generally gives:", ["A warning", "A mandatory instruction", "A tourist direction", "A temporary diversion"], 1),
            ("A red circle with a diagonal bar generally indicates:", ["A facility", "A prohibition or restriction", "A route direction", "A hospital"], 1),
            ("A sign showing children crossing warns of:", ["A school or children crossing area", "A fuel station", "A railway platform", "A parking area"], 0),
        ],
    },
    "road_rules": {
        "name": "Road Knowledge and Rules",
        "questions": [
            ("At a pedestrian crossing, a driver should:", ["Speed up", "Give way to pedestrians", "Use the horn continuously", "Park on the crossing"], 1),
            ("Before changing lanes, a driver should:", ["Check mirrors and blind spot, signal, then move when safe", "Move first and signal later", "Only sound the horn", "Brake suddenly"], 0),
            ("When an ambulance approaches with its siren on, you should:", ["Race ahead", "Give way safely", "Block the road", "Follow closely"], 1),
            ("A seat belt should be worn:", ["Only on highways", "Only by the driver", "By occupants as required, on every trip", "Only at night"], 2),
            ("Using a handheld mobile phone while driving is:", ["Safe at low speed", "Distracting and unsafe", "Required at junctions", "Allowed in heavy traffic"], 1),
        ],
    },
    "lane_discipline": {
        "name": "Lane Discipline",
        "questions": [
            ("Before overtaking, you must:", ["Check the road is clear and overtaking is permitted", "Follow the vehicle closely", "Overtake at a blind curve", "Ignore road markings"], 0),
            ("A lane change should be made:", ["Without checking", "After checking mirrors/blind spot and signalling", "Only by sounding the horn", "Suddenly"], 1),
            ("At a roundabout, drivers should:", ["Follow the signs and give way as required", "Drive against traffic", "Stop in the circle", "Overtake inside the circle"], 0),
            ("When being overtaken, you should:", ["Increase speed", "Maintain a steady course and not obstruct", "Move unpredictably", "Close the gap"], 1),
            ("You should avoid overtaking:", ["On a clear straight road when permitted", "Near blind bends and where prohibited", "When visibility is good", "When the road is wide"], 1),
        ],
    },
    "road_markings": {
        "name": "Road Markings",
        "questions": [
            ("A stop line at a junction tells you to:", ["Stop before the line when required", "Park on the line", "Change lanes", "Increase speed"], 0),
            ("A zebra crossing is intended for:", ["Pedestrians to cross", "Vehicle parking", "Overtaking", "U-turns only"], 0),
            ("Directional arrows painted on a lane indicate:", ["Permitted direction of movement", "Vehicle colour", "Road ownership", "Fuel level"], 0),
            ("You should obey solid lane markings because they:", ["Are decorative", "Restrict or guide lane movement", "Show parking fees", "Mark speed breakers only"], 1),
            ("A hatched/chevron area should generally be:", ["Used for overtaking", "Kept clear unless specifically permitted", "Used for parking", "Used to stop for calls"], 1),
        ],
    },
    "warning_lights": {
        "name": "Vehicle Warning Lights",
        "questions": [
            ("A red oil-pressure warning light while driving means you should:", ["Ignore it", "Stop safely as soon as possible and switch off the engine", "Accelerate", "Turn on the radio"], 1),
            ("A red engine temperature warning may indicate:", ["Engine overheating", "Low washer fluid", "Door open", "High beam on"], 0),
            ("An ABS warning light that stays on may indicate:", ["An ABS system fault", "A full fuel tank", "Indicators are on", "The handbrake is released"], 0),
            ("A battery/charging warning light while the engine is running may indicate:", ["Charging system trouble", "Tyre pressure is correct", "High engine oil level", "Seat belt is fastened"], 0),
            ("A blue high-beam indicator means:", ["High-beam headlights are on", "Engine is cold", "Fuel is low", "Parking brake is on"], 0),
        ],
    },
}

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_brand():
    return {"brand_primary": "Viva Toyota", "brand_secondary": "TDRIVE", "today": date.today().isoformat()}

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email, phone=phone, role="student")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your student account is ready.", "success")
            return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, active=True).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect, or the account is inactive.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        total_students = User.query.filter_by(role="student").count()
        total_staff = User.query.filter_by(role="staff").count()
        upcoming = Booking.query.filter(Booking.class_date >= date.today(), Booking.status == "confirmed").order_by(Booking.class_date, Booking.time_slot).limit(12).all()
        return render_template("admin_dashboard.html", total_students=total_students, total_staff=total_staff, upcoming=upcoming)
    if current_user.role == "staff":
        upcoming = Booking.query.filter(Booking.class_date >= date.today(), Booking.status == "confirmed").order_by(Booking.class_date, Booking.time_slot).limit(50).all()
        return render_template("staff_dashboard.html", upcoming=upcoming)
    bookings = Booking.query.filter_by(student_id=current_user.id).order_by(Booking.class_date.desc(), Booking.time_slot.desc()).all()
    scores = QuizScore.query.filter_by(student_id=current_user.id).order_by(QuizScore.completed_at.desc()).limit(5).all()
    return render_template("student_dashboard.html", bookings=bookings, scores=scores)

@app.route("/book", methods=["GET", "POST"])
@role_required("student")
def book():
    if request.method == "POST":
        class_type = request.form.get("class_type")
        raw_date = request.form.get("class_date", "")
        slot = request.form.get("time_slot", "")
        try:
            chosen_date = date.fromisoformat(raw_date)
        except ValueError:
            chosen_date = None
        slots = PRACTICAL_SLOTS if class_type == "practical" else SIMULATOR_SLOTS if class_type == "simulator" else []
        days = PRACTICAL_DAYS if class_type == "practical" else SIMULATOR_DAYS if class_type == "simulator" else set()
        if not chosen_date or chosen_date < date.today():
            flash("Choose today or a future date.", "error")
        elif chosen_date.weekday() not in days:
            flash("This class type is not available on the selected day.", "error")
        elif slot not in slots:
            flash("Please select a valid time slot.", "error")
        elif Booking.query.filter_by(class_type=class_type, class_date=chosen_date, time_slot=slot, status="confirmed").first():
            flash("That time slot has already been booked. Please choose another.", "error")
        else:
            booking = Booking(student_id=current_user.id, class_type=class_type, class_date=chosen_date, time_slot=slot)
            db.session.add(booking)
            db.session.commit()
            flash("Your booking has been submitted and confirmed.", "success")
            return redirect(url_for("dashboard"))
    return render_template("book.html", practical_slots=PRACTICAL_SLOTS, simulator_slots=SIMULATOR_SLOTS)

@app.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@role_required("student", "admin")
def cancel_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        flash("Booking not found.", "error")
    elif current_user.role != "admin" and booking.student_id != current_user.id:
        flash("You cannot cancel another student's booking.", "error")
    else:
        booking.status = "cancelled"
        db.session.commit()
        flash("Booking cancelled.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/bookings")
@role_required("admin")
def admin_bookings():
    bookings = Booking.query.order_by(Booking.class_date.desc(), Booking.time_slot).all()
    return render_template("admin_bookings.html", bookings=bookings)

@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "staff")
        password = request.form.get("password", "")
        if role not in ("admin", "staff") or not name or not email or len(password) < 8:
            flash("Provide valid details. Staff/admin passwords must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email address is already registered.", "error")
        else:
            user = User(name=name, email=email, phone=phone, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f"{role.title()} account created.", "success")
            return redirect(url_for("admin_users"))
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user or user.id == current_user.id:
        flash("That account cannot be changed.", "error")
    else:
        user.active = not user.active
        db.session.commit()
        flash("Account status updated.", "success")
    return redirect(url_for("admin_users"))

@app.route("/quiz")
@role_required("student")
def quiz_home():
    return render_template("quiz_home.html", categories=QUIZ_DATA)

@app.route("/quiz/<category>", methods=["GET", "POST"])
@role_required("student")
def take_quiz(category):
    quiz = QUIZ_DATA.get(category)
    if not quiz:
        flash("Quiz category not found.", "error")
        return redirect(url_for("quiz_home"))
    if request.method == "POST":
        score = 0
        for i, question in enumerate(quiz["questions"]):
            if request.form.get(f"q{i}") == str(question[2]):
                score += 1
        total = len(quiz["questions"])
        result = QuizScore(student_id=current_user.id, category=quiz["name"], score=score, total=total, percentage=round(score / total * 100, 1))
        db.session.add(result)
        db.session.commit()
        return render_template("quiz_result.html", quiz=quiz, score=score, total=total, percentage=result.percentage)
    return render_template("quiz.html", category=category, quiz=quiz)

@app.route("/admin")
@role_required("admin")
def admin_alias():
    return redirect(url_for("dashboard"))

@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    db.create_all()
    click.echo("TDRIVE database tables created.")

@app.cli.command("create-admin")
@click.option("--name", prompt="Admin name")
@click.option("--email", prompt="Admin email")
@click.password_option()
def create_admin(name, email, password):
    """Create the first administrator account."""
    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        click.echo("An account with that email already exists.")
        return
    user = User(name=name, email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Administrator account created for {email}.")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
