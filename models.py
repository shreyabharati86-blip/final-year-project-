import sqlite3
from datetime import datetime
from types import SimpleNamespace

from flask import current_app, g


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            education TEXT DEFAULT '',
            skills TEXT DEFAULT '',
            experience TEXT DEFAULT '',
            resume_filename TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES user(id)
        );

        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            industry TEXT DEFAULT '',
            description TEXT DEFAULT '',
            approved INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES user(id)
        );

        CREATE TABLE IF NOT EXISTS job (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            job_type TEXT NOT NULL,
            location TEXT DEFAULT 'Remote',
            salary TEXT DEFAULT '',
            required_skills TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES company(id)
        );

        CREATE TABLE IF NOT EXISTS application (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES job(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES user(id)
        );

        CREATE TABLE IF NOT EXISTS course (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            FOREIGN KEY (company_id) REFERENCES company(id)
        );
        """
    )
    db.commit()


def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def as_obj(row):
    if row is None:
        return None
    data = dict(row)
    if "is_active" in data and data["is_active"] is not None:
        data["is_active"] = bool(data["is_active"])
    if "approved" in data and data["approved"] is not None:
        data["approved"] = bool(data["approved"])
    for key in ("created_at", "applied_at"):
        if key in data:
            data[key] = parse_dt(data[key])
    return SimpleNamespace(**data)


def fetchone(sql, params=()):
    return as_obj(get_db().execute(sql, params).fetchone())


def fetchall(sql, params=()):
    return [as_obj(row) for row in get_db().execute(sql, params).fetchall()]


def execute(sql, params=()):
    cur = get_db().execute(sql, params)
    get_db().commit()
    return cur


def count_sql(sql, params=()):
    row = get_db().execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def has_users():
    return count_sql("SELECT COUNT(*) FROM user") > 0


def get_user(user_id, with_profile=True, with_company=True):
    user = fetchone("SELECT * FROM user WHERE id = ?", (user_id,))
    if not user:
        return None
    user.profile = get_profile_by_user(user.id) if with_profile else None
    user.company = get_company_by_user(user.id) if with_company else None
    return user


def get_user_by_email(email):
    user = fetchone("SELECT * FROM user WHERE email = ?", (email,))
    if not user:
        return None
    user.profile = get_profile_by_user(user.id)
    user.company = get_company_by_user(user.id)
    return user


def create_user(name, email, password_hash, role, is_active=True):
    cur = execute(
        """
        INSERT INTO user (name, email, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, email, password_hash, role, 1 if is_active else 0, now_str()),
    )
    return cur.lastrowid


def update_user_name(user_id, name):
    execute("UPDATE user SET name = ? WHERE id = ?", (name, user_id))


def toggle_user_active(user_id):
    user = fetchone("SELECT * FROM user WHERE id = ?", (user_id,))
    if not user or user.role == "admin":
        return None
    new_value = 0 if user.is_active else 1
    execute("UPDATE user SET is_active = ? WHERE id = ?", (new_value, user_id))
    user.is_active = bool(new_value)
    return user


def list_users():
    return fetchall("SELECT * FROM user ORDER BY created_at DESC")


def count_candidates():
    return count_sql("SELECT COUNT(*) FROM user WHERE role = 'candidate'")


def get_profile_by_user(user_id):
    return fetchone("SELECT * FROM profile WHERE user_id = ?", (user_id,))


def get_profile_by_resume(filename):
    return fetchone("SELECT * FROM profile WHERE resume_filename = ?", (filename,))


def create_profile(user_id, education="", skills="", experience="", resume_filename=""):
    cur = execute(
        """
        INSERT INTO profile (user_id, education, skills, experience, resume_filename)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, education, skills, experience, resume_filename),
    )
    return cur.lastrowid


def update_profile(profile_id, education, skills, experience, resume_filename):
    execute(
        """
        UPDATE profile
        SET education = ?, skills = ?, experience = ?, resume_filename = ?
        WHERE id = ?
        """,
        (education, skills, experience, resume_filename, profile_id),
    )


def get_company(company_id, with_user=False):
    company = fetchone("SELECT * FROM company WHERE id = ?", (company_id,))
    if company and with_user:
        company.user = get_user(company.user_id, with_profile=False, with_company=False)
    return company


def get_company_by_user(user_id):
    return fetchone("SELECT * FROM company WHERE user_id = ?", (user_id,))


def create_company(user_id, name, industry="", description="", approved=False):
    cur = execute(
        """
        INSERT INTO company (user_id, name, industry, description, approved)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, name, industry, description, 1 if approved else 0),
    )
    return cur.lastrowid


def approve_company(company_id):
    company = get_company(company_id)
    if not company:
        return None
    execute("UPDATE company SET approved = 1 WHERE id = ?", (company_id,))
    company.approved = True
    return company


def list_companies():
    companies = fetchall("SELECT * FROM company ORDER BY id DESC")
    for company in companies:
        company.user = get_user(company.user_id, with_profile=False, with_company=False)
    return companies


def count_companies():
    return count_sql("SELECT COUNT(*) FROM company")


def count_approved_companies():
    return count_sql("SELECT COUNT(*) FROM company WHERE approved = 1")


def _attach_company(job):
    if job:
        job.company = get_company(job.company_id)
        job.applications = fetchall("SELECT id FROM application WHERE job_id = ?", (job.id,))
    return job


def list_public_jobs(q="", job_type="", limit=None):
    sql = """
        SELECT job.* FROM job
        JOIN company ON company.id = job.company_id
        WHERE company.approved = 1
    """
    params = []
    if q:
        like = "%" + q + "%"
        sql += """
            AND (
                job.title LIKE ? COLLATE NOCASE
                OR job.location LIKE ? COLLATE NOCASE
                OR job.required_skills LIKE ? COLLATE NOCASE
                OR company.name LIKE ? COLLATE NOCASE
            )
        """
        params.extend([like, like, like, like])
    if job_type in {"job", "internship"}:
        sql += " AND job.job_type = ?"
        params.append(job_type)
    sql += " ORDER BY job.created_at DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    jobs = fetchall(sql, params)
    for job in jobs:
        _attach_company(job)
    return jobs


def count_public_jobs():
    return count_sql(
        """
        SELECT COUNT(*) FROM job
        JOIN company ON company.id = job.company_id
        WHERE company.approved = 1
        """
    )


def get_public_job(job_id):
    job = fetchone(
        """
        SELECT job.* FROM job
        JOIN company ON company.id = job.company_id
        WHERE job.id = ? AND company.approved = 1
        """,
        (job_id,),
    )
    return _attach_company(job)


def get_job(job_id):
    return _attach_company(fetchone("SELECT * FROM job WHERE id = ?", (job_id,)))


def list_jobs_for_company(company_id):
    jobs = fetchall(
        "SELECT * FROM job WHERE company_id = ? ORDER BY created_at DESC",
        (company_id,),
    )
    for job in jobs:
        _attach_company(job)
    return jobs


def list_all_jobs():
    jobs = fetchall("SELECT * FROM job ORDER BY created_at DESC")
    for job in jobs:
        _attach_company(job)
    return jobs


def create_job(company_id, title, job_type, location, salary, required_skills, description):
    cur = execute(
        """
        INSERT INTO job (
            company_id, title, job_type, location, salary, required_skills, description, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, title, job_type, location, salary, required_skills, description, now_str()),
    )
    return cur.lastrowid


def delete_job(job_id):
    job = get_job(job_id)
    if not job:
        return False
    execute("DELETE FROM job WHERE id = ?", (job_id,))
    return True


def count_jobs():
    return count_sql("SELECT COUNT(*) FROM job")


def get_application(job_id, user_id):
    return fetchone(
        "SELECT * FROM application WHERE job_id = ? AND user_id = ?",
        (job_id, user_id),
    )


def _hydrate_application(app, with_job=True, with_candidate=True):
    if not app:
        return None
    if with_job:
        app.job = get_job(app.job_id)
        if app.job:
            app.job.company = get_company(app.job.company_id)
    if with_candidate:
        app.candidate = get_user(app.user_id, with_profile=True, with_company=False)
    return app


def create_application(job_id, user_id, status="pending"):
    cur = execute(
        """
        INSERT INTO application (job_id, user_id, status, applied_at)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, user_id, status, now_str()),
    )
    return cur.lastrowid


def list_applications_for_user(user_id):
    apps = fetchall(
        "SELECT * FROM application WHERE user_id = ? ORDER BY applied_at DESC",
        (user_id,),
    )
    return [_hydrate_application(app, with_candidate=False) for app in apps]


def list_applications_for_company(company_id, job_id=None):
    sql = """
        SELECT application.* FROM application
        JOIN job ON job.id = application.job_id
        WHERE job.company_id = ?
    """
    params = [company_id]
    if job_id:
        sql += " AND application.job_id = ?"
        params.append(job_id)
    sql += " ORDER BY application.applied_at DESC"
    return [_hydrate_application(app) for app in fetchall(sql, params)]


def get_company_application(app_id, company_id):
    app = fetchone(
        """
        SELECT application.* FROM application
        JOIN job ON job.id = application.job_id
        WHERE application.id = ? AND job.company_id = ?
        """,
        (app_id, company_id),
    )
    return _hydrate_application(app)


def update_application_status(app_id, status):
    execute("UPDATE application SET status = ? WHERE id = ?", (status, app_id))


def count_company_applications(company_id, status=None):
    sql = """
        SELECT COUNT(*) FROM application
        JOIN job ON job.id = application.job_id
        WHERE job.company_id = ?
    """
    params = [company_id]
    if status:
        sql += " AND application.status = ?"
        params.append(status)
    return count_sql(sql, params)


def company_can_view_resume(company_id, candidate_user_id):
    return (
        count_sql(
            """
            SELECT COUNT(*) FROM application
            JOIN job ON job.id = application.job_id
            WHERE application.user_id = ? AND job.company_id = ?
            """,
            (candidate_user_id, company_id),
        )
        > 0
    )


def list_all_applications():
    apps = fetchall("SELECT * FROM application ORDER BY applied_at DESC")
    return [_hydrate_application(app) for app in apps]


def count_applications():
    return count_sql("SELECT COUNT(*) FROM application")


def list_public_courses():
    courses = fetchall(
        """
        SELECT course.* FROM course
        JOIN company ON company.id = course.company_id
        WHERE company.approved = 1
        """
    )
    for course in courses:
        course.company = get_company(course.company_id)
    return courses


def list_courses_for_company(company_id):
    return fetchall("SELECT * FROM course WHERE company_id = ?", (company_id,))


def list_all_courses():
    courses = fetchall("SELECT * FROM course")
    for course in courses:
        course.company = get_company(course.company_id)
    return courses


def create_course(company_id, skill, title, description=""):
    cur = execute(
        """
        INSERT INTO course (company_id, skill, title, description)
        VALUES (?, ?, ?, ?)
        """,
        (company_id, skill, title, description),
    )
    return cur.lastrowid
