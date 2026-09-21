import os
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import models as db
from seed import seed_if_empty

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "resumes")
ALLOWED_RESUME = {"pdf", "doc", "docx"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "hirehub-dev-secret-change-later"
app.config["DATABASE"] = os.path.join(BASE_DIR, "jobportal.db")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.teardown_appcontext(db.close_db)


def split_skills(text):
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def skill_set(text):
    return {item.lower() for item in split_skills(text)}


def get_current_user():
    if "current_user" not in g:
        user_id = session.get("user_id")
        g.current_user = db.get_user(user_id) if user_id else None
    return g.current_user


@app.context_processor
def inject_globals():
    return {"current_user": get_current_user()}


def destination_for_user(user):
    if not user:
        return url_for("index")
    if user.role == "admin":
        return url_for("admin_dashboard")
    if user.role == "company":
        return url_for("company_dashboard")
    return url_for("profile")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Please login first.", "warning")
                if roles == ("admin",):
                    return redirect(url_for("admin_login"))
                return redirect(url_for("login"))
            if user.role not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(destination_for_user(user))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@app.route("/")
def index():
    jobs = db.list_public_jobs(limit=6)
    return render_template(
        "index.html",
        jobs=jobs,
        job_count=db.count_public_jobs(),
        company_count=db.count_approved_companies(),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "candidate")
        company_name = request.form.get("company_name", "").strip()

        if not name or not email or not password:
            flash("Fill all required fields.", "danger")
            return render_template("register.html")
        if role not in {"candidate", "company"}:
            flash("Choose a valid role.", "danger")
            return render_template("register.html")
        if role == "company" and not company_name:
            flash("Company name is required.", "danger")
            return render_template("register.html")
        if db.get_user_by_email(email):
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        user_id = db.create_user(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
        )
        if role == "candidate":
            db.create_profile(user_id=user_id)
        else:
            db.create_company(
                user_id=user_id,
                name=company_name,
                industry=request.form.get("industry", "").strip(),
                approved=False,
            )
        flash("Account created. You can login now.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    current = get_current_user()
    if current:
        return redirect(destination_for_user(current))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        if user.role == "admin":
            flash("Administrator accounts must sign in through the admin portal.", "warning")
            return render_template("login.html")
        if not user.is_active:
            flash("This account is blocked. Contact admin.", "danger")
            return render_template("login.html")
        session["user_id"] = user.id
        flash("Welcome back, %s." % user.name, "success")
        if user.role == "company":
            return redirect(url_for("company_dashboard"))
        return redirect(url_for("profile"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/jobs")
def jobs():
    q = request.args.get("q", "").strip()
    job_type = request.args.get("type", "").strip()
    jobs_list = db.list_public_jobs(q=q, job_type=job_type)
    return render_template("jobs.html", jobs=jobs_list, q=q, job_type=job_type)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = db.get_public_job(job_id)
    if not job:
        abort(404)
    user = get_current_user()
    existing = None
    missing_skills = []
    recommended = []
    if user and user.role == "candidate" and user.profile:
        user_skills = skill_set(user.profile.skills)
        existing = db.get_application(job.id, user.id)
        required = split_skills(job.required_skills)
        missing_skills = [skill for skill in required if skill.lower() not in user_skills]
        if missing_skills:
            missing_lower = {skill.lower() for skill in missing_skills}
            recommended = [
                course
                for course in db.list_courses_for_company(job.company_id)
                if course.skill.lower() in missing_lower
            ]
    return render_template(
        "job_detail.html",
        job=job,
        existing=existing,
        missing_skills=missing_skills,
        recommended=recommended,
        required_skills=split_skills(job.required_skills),
    )


@app.route("/jobs/<int:job_id>/apply", methods=["POST"])
@role_required("candidate")
def apply_job(job_id):
    user = get_current_user()
    job = db.get_public_job(job_id)
    if not job:
        abort(404)
    if not user.profile or not user.profile.resume_filename:
        flash("Upload your resume in Profile before applying.", "warning")
        return redirect(url_for("profile"))
    existing = db.get_application(job.id, user.id)
    if existing:
        flash("You already applied for this opening.", "info")
        return redirect(url_for("job_detail", job_id=job.id))
    db.create_application(job.id, user.id, status="pending")
    flash("Application submitted.", "success")
    return redirect(url_for("my_applications"))


@app.route("/profile", methods=["GET", "POST"])
@role_required("candidate")
def profile():
    user = get_current_user()
    if not user.profile:
        db.create_profile(user_id=user.id)
        user.profile = db.get_profile_by_user(user.id)
    if request.method == "POST":
        name = request.form.get("name", user.name).strip() or user.name
        education = request.form.get("education", "").strip()
        skills = request.form.get("skills", "").strip()
        experience = request.form.get("experience", "").strip()
        resume_filename = user.profile.resume_filename or ""
        resume = request.files.get("resume")
        if resume and resume.filename:
            ext = resume.filename.rsplit(".", 1)[-1].lower() if "." in resume.filename else ""
            if ext not in ALLOWED_RESUME:
                flash("Resume must be PDF, DOC, or DOCX.", "danger")
                return redirect(url_for("profile"))
            filename = secure_filename("user_%s_%s" % (user.id, resume.filename))
            resume.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            resume_filename = filename
        db.update_user_name(user.id, name)
        db.update_profile(
            user.profile.id,
            education,
            skills,
            experience,
            resume_filename,
        )
        flash("Profile saved.", "success")
        return redirect(url_for("profile"))
    apps = db.list_applications_for_user(user.id)
    return render_template("profile.html", profile=user.profile, apps=apps)


@app.route("/applications")
@role_required("candidate")
def my_applications():
    user = get_current_user()
    apps = db.list_applications_for_user(user.id)
    return render_template("applications.html", applications=apps)


@app.route("/courses")
def courses():
    items = db.list_public_courses()
    return render_template("courses.html", courses=items)


@app.route("/uploads/resumes/<filename>")
@login_required
def uploaded_resume(filename):
    user = get_current_user()
    if user.role == "candidate" and (
        not user.profile or user.profile.resume_filename != filename
    ):
        flash("You can only open your own resume.", "danger")
        return redirect(url_for("profile"))
    if user.role == "company":
        owner = db.get_profile_by_resume(filename)
        allowed = False
        if owner and user.company:
            allowed = db.company_can_view_resume(user.company.id, owner.user_id)
        if not allowed:
            flash("Resume not available.", "danger")
            return redirect(url_for("company_applicants"))
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/company")
@role_required("company")
def company_dashboard():
    company = get_current_user().company
    jobs_list = db.list_jobs_for_company(company.id)
    return render_template(
        "company/dashboard.html",
        company=company,
        jobs=jobs_list,
        app_count=db.count_company_applications(company.id),
        pending=db.count_company_applications(company.id, status="pending"),
    )


@app.route("/company/jobs/new", methods=["GET", "POST"])
@role_required("company")
def post_job():
    company = get_current_user().company
    if not company.approved:
        flash("Admin must approve your company before you can post jobs.", "warning")
        return redirect(url_for("company_dashboard"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Job title is required.", "danger")
            return render_template("company/post_job.html")
        db.create_job(
            company_id=company.id,
            title=title,
            job_type=request.form.get("job_type", "job"),
            location=request.form.get("location", "").strip() or "Remote",
            salary=request.form.get("salary", "").strip(),
            required_skills=request.form.get("required_skills", "").strip(),
            description=request.form.get("description", "").strip(),
        )
        flash("Vacancy posted.", "success")
        return redirect(url_for("company_dashboard"))
    return render_template("company/post_job.html")


@app.route("/company/applicants")
@role_required("company")
def company_applicants():
    company = get_current_user().company
    job_id = request.args.get("job_id", type=int)
    apps = db.list_applications_for_company(company.id, job_id=job_id)
    jobs_list = db.list_jobs_for_company(company.id)
    return render_template(
        "company/applicants.html",
        applications=apps,
        jobs=jobs_list,
        selected_job=job_id,
    )


@app.route("/company/applications/<int:app_id>/status", methods=["POST"])
@role_required("company")
def update_application_status(app_id):
    company = get_current_user().company
    application = db.get_company_application(app_id, company.id)
    if not application:
        abort(404)
    status = request.form.get("status")
    if status not in {"accepted", "rejected", "pending"}:
        flash("Invalid status.", "danger")
        return redirect(url_for("company_applicants"))
    db.update_application_status(application.id, status)
    flash("Application %s." % status, "success")
    return redirect(url_for("company_applicants"))


@app.route("/company/courses", methods=["GET", "POST"])
@role_required("company")
def company_courses():
    company = get_current_user().company
    if not company.approved:
        flash("Admin must approve your company first.", "warning")
        return redirect(url_for("company_dashboard"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        skill = request.form.get("skill", "").strip()
        if not title or not skill:
            flash("Course title and skill are required.", "danger")
        else:
            db.create_course(
                company_id=company.id,
                title=title,
                skill=skill,
                description=request.form.get("description", "").strip(),
            )
            flash("Course added. Candidates missing this skill will see it.", "success")
            return redirect(url_for("company_courses"))
    items = db.list_courses_for_company(company.id)
    return render_template("company/courses.html", courses=items)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    current = get_current_user()
    if current:
        if current.role == "admin":
            return redirect(url_for("admin_dashboard"))
        flash("The administration portal is for administrators only.", "danger")
        return redirect(destination_for_user(current))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid admin email or password.", "danger")
            return render_template("admin/login.html")
        if user.role != "admin":
            flash("Access denied. This portal is for administrators only.", "danger")
            return render_template("admin/login.html")
        if not user.is_active:
            flash("This administrator account is blocked.", "danger")
            return render_template("admin/login.html")
        session["user_id"] = user.id
        flash("Welcome back, %s." % user.name, "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        users=db.list_users(),
        companies=db.list_companies(),
        jobs=db.list_all_jobs(),
        applications=db.list_all_applications(),
        courses=db.list_all_courses(),
        stats={
            "candidates": db.count_candidates(),
            "companies": db.count_companies(),
            "jobs": db.count_jobs(),
            "applications": db.count_applications(),
        },
    )


@app.route("/admin/analytics")
@role_required("admin")
def admin_analytics():
    company_id = request.args.get("company_id", type=int)
    job_type = request.args.get("job_type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    analytics = db.get_admin_analytics(
        company_id=company_id,
        job_type=job_type,
        date_from=date_from,
        date_to=date_to,
    )
    return render_template("admin/analytics.html", analytics=analytics)


@app.route("/admin/database")
@role_required("admin")
def admin_database():
    return render_template(
        "admin/database.html",
        overview=db.get_database_overview(),
        table_data=None,
    )


@app.route("/admin/database/<table_name>")
@role_required("admin")
def admin_database_table(table_name):
    table_name = (table_name or "").strip().lower()
    result = db.inspect_table(
        table_name,
        search=request.args.get("q", ""),
        page=request.args.get("page", 1, type=int) or 1,
    )
    if result is None:
        abort(404)
    return render_template(
        "admin/database.html",
        overview=db.get_database_overview(),
        table_data=result,
    )


@app.route("/admin/company/<int:company_id>/approve", methods=["POST"])
@role_required("admin")
def approve_company(company_id):
    company = db.approve_company(company_id)
    if not company:
        flash("Company not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    flash("%s approved." % company.name, "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/job/<int:job_id>/delete", methods=["POST"])
@role_required("admin")
def admin_delete_job(job_id):
    if db.delete_job(job_id):
        flash("Job removed.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/user/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    user = db.toggle_user_active(user_id)
    if user:
        flash("%s is now %s." % (user.name, "active" if user.is_active else "blocked"), "info")
    return redirect(url_for("admin_dashboard"))


with app.app_context():
    db.init_db()
    seed_if_empty()


if __name__ == "__main__":
    app.run(debug=True)
