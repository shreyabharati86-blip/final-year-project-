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


# --- Admin analytics and read-only database viewer ---

INSPECTOR_TABLES = {
    "user": {
        "label": "Users",
        "base_from": "user",
        "select": "id, name, email, role, is_active, created_at",
        "keys": ["id", "name", "email", "role", "is_active", "created_at"],
        "headers": ["ID", "Name", "Email", "Role", "Status", "Created"],
        "search": ["name", "email", "role"],
        "order": "id DESC",
    },
    "profile": {
        "label": "Profiles",
        "base_from": "profile JOIN user ON user.id = profile.user_id",
        "select": (
            "profile.id AS id, user.name AS candidate, user.email AS email, "
            "profile.education AS education, profile.skills AS skills, "
            "profile.experience AS experience, profile.resume_filename AS resume"
        ),
        "keys": ["id", "candidate", "email", "education", "skills", "experience", "resume"],
        "headers": ["ID", "Candidate", "Email", "Education", "Skills", "Experience", "Resume"],
        "search": [
            "user.name",
            "user.email",
            "profile.education",
            "profile.skills",
            "profile.experience",
        ],
        "order": "profile.id DESC",
    },
    "company": {
        "label": "Companies",
        "base_from": "company JOIN user ON user.id = company.user_id",
        "select": (
            "company.id AS id, company.name AS name, company.industry AS industry, "
            "user.email AS owner_email, company.approved AS approved, "
            "company.description AS description"
        ),
        "keys": ["id", "name", "industry", "owner_email", "approved", "description"],
        "headers": ["ID", "Company", "Industry", "Owner", "Approved", "Description"],
        "search": ["company.name", "company.industry", "user.email", "company.description"],
        "order": "company.id DESC",
    },
    "job": {
        "label": "Jobs",
        "base_from": "job JOIN company ON company.id = job.company_id",
        "select": (
            "job.id AS id, job.title AS title, company.name AS company, "
            "job.job_type AS job_type, job.location AS location, job.salary AS salary, "
            "job.required_skills AS required_skills, job.created_at AS created_at"
        ),
        "keys": [
            "id",
            "title",
            "company",
            "job_type",
            "location",
            "salary",
            "required_skills",
            "created_at",
        ],
        "headers": ["ID", "Title", "Company", "Type", "Location", "Salary", "Skills", "Created"],
        "search": [
            "job.title",
            "company.name",
            "job.job_type",
            "job.location",
            "job.required_skills",
        ],
        "order": "job.id DESC",
    },
    "application": {
        "label": "Applications",
        "base_from": (
            "application "
            "JOIN user ON user.id = application.user_id "
            "JOIN job ON job.id = application.job_id"
        ),
        "select": (
            "application.id AS id, user.name AS candidate, job.title AS job, "
            "application.status AS status, application.applied_at AS applied_at"
        ),
        "keys": ["id", "candidate", "job", "status", "applied_at"],
        "headers": ["ID", "Candidate", "Job", "Status", "Applied"],
        "search": ["user.name", "job.title", "application.status"],
        "order": "application.id DESC",
    },
    "course": {
        "label": "Courses",
        "base_from": "course JOIN company ON company.id = course.company_id",
        "select": (
            "course.id AS id, course.title AS title, course.skill AS skill, "
            "company.name AS company, course.description AS description"
        ),
        "keys": ["id", "title", "skill", "company", "description"],
        "headers": ["ID", "Course", "Skill", "Company", "Description"],
        "search": ["course.title", "course.skill", "company.name", "course.description"],
        "order": "course.id DESC",
    },
}

_STATUS_ORDER = ("pending", "accepted", "rejected")
_STATUS_LABELS = {
    "pending": "Pending",
    "accepted": "Accepted",
    "rejected": "Rejected",
}


def _where(clauses):
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


def _iso_date(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        return None


def _label_rows(sql, params=()):
    rows = get_db().execute(sql, params).fetchall()
    items = []
    for row in rows:
        label = row[0]
        if label is None or str(label).strip() == "":
            label = "Unspecified"
        items.append({"label": str(label), "count": int(row[1])})
    return items


def _top_n_with_other(items, limit=8):
    if len(items) <= limit:
        return items
    head = items[:limit]
    other = sum(item["count"] for item in items[limit:])
    if other:
        head.append({"label": "Other", "count": other})
    return head


def _aggregate_skill_strings(values, limit=10):
    counts = {}
    display = {}
    for text in values:
        if not text:
            continue
        for part in str(text).split(","):
            skill = part.strip()
            if not skill:
                continue
            key = skill.lower()
            counts[key] = counts.get(key, 0) + 1
            if key not in display:
                display[key] = skill
    items = [{"label": display[key], "count": counts[key]} for key in counts]
    items.sort(key=lambda item: (-item["count"], item["label"].lower()))
    return items[:limit] if limit else items


def _job_filter_clauses(company_id=None, job_type=None, alias="job"):
    clauses = []
    params = []
    if company_id:
        clauses.append("%s.company_id = ?" % alias)
        params.append(int(company_id))
    if job_type in {"job", "internship"}:
        clauses.append("%s.job_type = ?" % alias)
        params.append(job_type)
    return clauses, params


def _application_filter_clauses(
    company_id=None, job_type=None, date_from=None, date_to=None
):
    clauses, params = _job_filter_clauses(company_id, job_type, alias="job")
    start = _iso_date(date_from)
    end = _iso_date(date_to)
    if start:
        clauses.append("date(application.applied_at) >= date(?)")
        params.append(start)
    if end:
        clauses.append("date(application.applied_at) <= date(?)")
        params.append(end)
    return clauses, params


def list_companies_for_filter():
    return fetchall("SELECT id, name FROM company ORDER BY name COLLATE NOCASE")


def get_overview_statistics():
    row = get_db().execute(
        """
        SELECT
            (SELECT COUNT(*) FROM user WHERE role = 'candidate') AS candidates,
            (SELECT COUNT(*) FROM company) AS companies,
            (SELECT COUNT(*) FROM company WHERE approved = 1) AS approved_companies,
            (SELECT COUNT(*) FROM company WHERE approved = 0) AS pending_companies,
            (SELECT COUNT(*) FROM job) AS jobs_total,
            (SELECT COUNT(*) FROM job WHERE job_type = 'job') AS jobs,
            (SELECT COUNT(*) FROM job WHERE job_type = 'internship') AS internships,
            (SELECT COUNT(*) FROM application) AS applications,
            (SELECT COUNT(*) FROM course) AS courses
        """
    ).fetchone()
    return {
        "candidates": int(row["candidates"]),
        "companies": int(row["companies"]),
        "approved_companies": int(row["approved_companies"]),
        "pending_companies": int(row["pending_companies"]),
        "jobs_total": int(row["jobs_total"]),
        "jobs": int(row["jobs"]),
        "internships": int(row["internships"]),
        "applications": int(row["applications"]),
        "courses": int(row["courses"]),
    }


def get_application_statistics(
    company_id=None, job_type=None, date_from=None, date_to=None
):
    clauses, params = _application_filter_clauses(
        company_id, job_type, date_from, date_to
    )
    sql = """
        SELECT application.status, COUNT(*)
        FROM application
        JOIN job ON job.id = application.job_id
        %s
        GROUP BY application.status
    """ % _where(clauses)
    found = {}
    for item in _label_rows(sql, params):
        found[item["label"].lower()] = item["count"]
    status = []
    for key in _STATUS_ORDER:
        status.append(
            {
                "label": _STATUS_LABELS[key],
                "key": key,
                "count": int(found.get(key, 0)),
            }
        )
    for key, count in found.items():
        if key not in _STATUS_ORDER:
            status.append({"label": key.title(), "key": key, "count": count})
    return {"status": status, "total": sum(item["count"] for item in status)}


def get_application_trend(
    company_id=None, job_type=None, date_from=None, date_to=None
):
    clauses, params = _application_filter_clauses(
        company_id, job_type, date_from, date_to
    )
    sql = """
        SELECT date(application.applied_at) AS day, COUNT(*)
        FROM application
        JOIN job ON job.id = application.job_id
        %s
        GROUP BY day
        ORDER BY day
    """ % _where(clauses)
    daily = _label_rows(sql, params)
    empty = {"granularity": "month", "labels": [], "counts": []}
    if not daily:
        return empty

    span_days = 0
    try:
        start = datetime.strptime(daily[0]["label"], "%Y-%m-%d")
        end = datetime.strptime(daily[-1]["label"], "%Y-%m-%d")
        span_days = (end - start).days
    except ValueError:
        span_days = len(daily)

    if len(daily) <= 45 and span_days <= 60:
        labels = []
        counts = []
        for item in daily:
            parsed = parse_dt(item["label"])
            labels.append(parsed.strftime("%d %b") if parsed else item["label"])
            counts.append(item["count"])
        return {"granularity": "day", "labels": labels, "counts": counts}

    months = {}
    for item in daily:
        key = item["label"][:7]
        months[key] = months.get(key, 0) + item["count"]
    labels = []
    counts = []
    for key in sorted(months):
        parsed = parse_dt(key + "-01")
        labels.append(parsed.strftime("%b %Y") if parsed else key)
        counts.append(months[key])
    return {"granularity": "month", "labels": labels, "counts": counts}


def get_job_statistics(company_id=None, job_type=None):
    clauses, params = _job_filter_clauses(company_id, job_type)
    where_sql = _where(clauses)

    type_counts = {item["label"].lower(): item["count"] for item in _label_rows(
        "SELECT job_type, COUNT(*) FROM job %s GROUP BY job_type" % where_sql,
        params,
    )}
    by_type = [
        {"label": "Jobs", "key": "job", "count": int(type_counts.get("job", 0))},
        {
            "label": "Internships",
            "key": "internship",
            "count": int(type_counts.get("internship", 0)),
        },
    ]
    for key, count in type_counts.items():
        if key not in {"job", "internship"}:
            by_type.append({"label": key.title(), "key": key, "count": count})

    company_sql = """
        SELECT company.name, COUNT(job.id)
        FROM company
        LEFT JOIN job ON job.company_id = company.id
    """
    company_clauses = []
    company_params = []
    if job_type in {"job", "internship"}:
        company_sql = """
            SELECT company.name, COUNT(job.id)
            FROM company
            LEFT JOIN job ON job.company_id = company.id AND job.job_type = ?
        """
        company_params.append(job_type)
    if company_id:
        company_clauses.append("company.id = ?")
        company_params.append(int(company_id))
    company_sql += _where(company_clauses)
    company_sql += (
        " GROUP BY company.id HAVING COUNT(job.id) > 0"
        " ORDER BY COUNT(job.id) DESC, company.name COLLATE NOCASE"
    )
    by_company = _label_rows(company_sql, company_params)

    location_sql = (
        "SELECT location, COUNT(*) FROM job %s GROUP BY location ORDER BY COUNT(*) DESC"
        % where_sql
    )
    by_location = _top_n_with_other(_label_rows(location_sql, params), limit=8)

    return {
        "by_type": by_type,
        "by_company": by_company,
        "by_location": by_location,
        "total": sum(item["count"] for item in by_type),
    }


def get_skill_statistics(company_id=None, job_type=None):
    clauses, params = _job_filter_clauses(company_id, job_type)
    rows = get_db().execute(
        "SELECT required_skills FROM job" + _where(clauses),
        params,
    ).fetchall()
    return {"in_demand": _aggregate_skill_strings([row[0] for row in rows], limit=10)}


def get_candidate_statistics():
    total = count_candidates()
    row = get_db().execute(
        """
        SELECT
            SUM(CASE WHEN profile.resume_filename IS NOT NULL
                      AND TRIM(profile.resume_filename) != '' THEN 1 ELSE 0 END) AS with_resume,
            SUM(CASE WHEN profile.resume_filename IS NULL
                      OR TRIM(profile.resume_filename) = '' THEN 1 ELSE 0 END) AS without_resume,
            SUM(CASE WHEN profile.experience IS NOT NULL
                      AND TRIM(profile.experience) != '' THEN 1 ELSE 0 END) AS with_experience,
            SUM(CASE WHEN profile.experience IS NULL
                      OR TRIM(profile.experience) = '' THEN 1 ELSE 0 END) AS without_experience
        FROM profile
        JOIN user ON user.id = profile.user_id
        WHERE user.role = 'candidate'
        """
    ).fetchone()
    with_resume = int(row["with_resume"] or 0)
    without_resume = int(row["without_resume"] or 0)
    missing_profiles = max(0, total - with_resume - without_resume)
    without_resume += missing_profiles

    education = _label_rows(
        """
        SELECT TRIM(profile.education) AS education, COUNT(*)
        FROM profile
        JOIN user ON user.id = profile.user_id
        WHERE user.role = 'candidate'
          AND profile.education IS NOT NULL
          AND TRIM(profile.education) != ''
        GROUP BY TRIM(profile.education)
        ORDER BY COUNT(*) DESC, education COLLATE NOCASE
        LIMIT 8
        """
    )
    skill_rows = get_db().execute(
        """
        SELECT profile.skills
        FROM profile
        JOIN user ON user.id = profile.user_id
        WHERE user.role = 'candidate'
        """
    ).fetchall()
    return {
        "total": total,
        "with_resume": with_resume,
        "without_resume": without_resume,
        "with_experience": int(row["with_experience"] or 0),
        "without_experience": int(row["without_experience"] or 0) + missing_profiles,
        "by_education": education,
        "skills": _aggregate_skill_strings([item[0] for item in skill_rows], limit=10),
        "resume": [
            {"label": "With resume", "count": with_resume},
            {"label": "Without resume", "count": without_resume},
        ],
        "experience": [
            {"label": "Has experience listed", "count": int(row["with_experience"] or 0)},
            {
                "label": "No experience listed",
                "count": int(row["without_experience"] or 0) + missing_profiles,
            },
        ],
    }


def get_company_statistics(company_id=None, job_type=None):
    clauses = []
    params = []
    if company_id:
        clauses.append("company.id = ?")
        params.append(int(company_id))
    where_sql = _where(clauses)

    job_join = "LEFT JOIN job ON job.company_id = company.id"
    job_params = list(params)
    app_join = "LEFT JOIN job ON job.company_id = company.id"
    app_params = list(params)
    if job_type in {"job", "internship"}:
        job_join = "LEFT JOIN job ON job.company_id = company.id AND job.job_type = ?"
        job_params = [job_type] + list(params)
        app_join = "LEFT JOIN job ON job.company_id = company.id AND job.job_type = ?"
        app_params = [job_type] + list(params)

    by_jobs = _label_rows(
        """
        SELECT company.name, COUNT(job.id)
        FROM company
        %s
        %s
        GROUP BY company.id
        HAVING COUNT(job.id) > 0
        ORDER BY COUNT(job.id) DESC, company.name COLLATE NOCASE
        """
        % (job_join, where_sql),
        job_params,
    )
    by_applications = _label_rows(
        """
        SELECT company.name, COUNT(application.id)
        FROM company
        %s
        LEFT JOIN application ON application.job_id = job.id
        %s
        GROUP BY company.id
        HAVING COUNT(application.id) > 0
        ORDER BY COUNT(application.id) DESC, company.name COLLATE NOCASE
        """
        % (app_join, where_sql),
        app_params,
    )
    by_courses = _label_rows(
        """
        SELECT company.name, COUNT(course.id)
        FROM company
        LEFT JOIN course ON course.company_id = company.id
        %s
        GROUP BY company.id
        HAVING COUNT(course.id) > 0
        ORDER BY COUNT(course.id) DESC, company.name COLLATE NOCASE
        """
        % where_sql,
        params,
    )
    by_industry = _label_rows(
        """
        SELECT CASE
                 WHEN industry IS NULL OR TRIM(industry) = '' THEN 'Unspecified'
                 ELSE TRIM(industry)
               END AS industry,
               COUNT(*)
        FROM company
        %s
        GROUP BY industry
        ORDER BY COUNT(*) DESC, industry COLLATE NOCASE
        """
        % where_sql,
        params,
    )
    return {
        "by_jobs": by_jobs,
        "by_applications": by_applications,
        "by_courses": by_courses,
        "by_industry": by_industry,
    }


def get_course_statistics(company_id=None):
    clauses = []
    params = []
    if company_id:
        clauses.append("course.company_id = ?")
        params.append(int(company_id))
    where_sql = _where(clauses)
    skill_rows = get_db().execute(
        "SELECT skill FROM course" + where_sql,
        params,
    ).fetchall()
    company_clauses = ["company.id = ?"] if company_id else []
    by_company = _label_rows(
        """
        SELECT company.name, COUNT(course.id)
        FROM company
        LEFT JOIN course ON course.company_id = company.id
        %s
        GROUP BY company.id
        HAVING COUNT(course.id) > 0
        ORDER BY COUNT(course.id) DESC, company.name COLLATE NOCASE
        """
        % _where(company_clauses),
        params,
    )
    total = count_sql("SELECT COUNT(*) FROM course" + where_sql, params)
    return {
        "total": total,
        "by_skill": _aggregate_skill_strings([row[0] for row in skill_rows], limit=10),
        "by_company": by_company,
    }


def get_admin_analytics(company_id=None, job_type=None, date_from=None, date_to=None):
    job_type = job_type if job_type in {"job", "internship"} else None
    company_id = int(company_id) if company_id else None
    date_from = _iso_date(date_from)
    date_to = _iso_date(date_to)
    return {
        "overview": get_overview_statistics(),
        "applications": get_application_statistics(
            company_id, job_type, date_from, date_to
        ),
        "trend": get_application_trend(company_id, job_type, date_from, date_to),
        "jobs": get_job_statistics(company_id, job_type),
        "skills": get_skill_statistics(company_id, job_type),
        "candidates": get_candidate_statistics(),
        "companies": get_company_statistics(company_id, job_type),
        "courses": get_course_statistics(company_id),
        "filters": {
            "company_id": company_id,
            "job_type": job_type or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
        "filter_companies": [
            {"id": company.id, "name": company.name}
            for company in list_companies_for_filter()
        ],
    }


def get_database_overview():
    items = []
    for key, meta in INSPECTOR_TABLES.items():
        items.append(
            {
                "key": key,
                "label": meta["label"],
                "count": count_sql("SELECT COUNT(*) FROM %s" % key),
            }
        )
    return items


def _format_inspect_value(key, value):
    if key == "is_active":
        return "Active" if value else "Blocked"
    if key == "approved":
        return "Yes" if value else "No"
    if key in {"role", "job_type", "status"} and value:
        return str(value).replace("_", " ").capitalize()
    if key in {"created_at", "applied_at"}:
        parsed = parse_dt(value)
        return parsed.strftime("%d %b %Y %H:%M") if parsed else (value or "—")
    if key == "resume":
        return value if value else "—"
    if value is None or str(value).strip() == "":
        return "—"
    text = str(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def inspect_table(table_name, search="", page=1, per_page=20):
    meta = INSPECTOR_TABLES.get(table_name)
    if not meta:
        return None
    search = (search or "").strip()[:80]
    page = max(1, int(page or 1))
    per_page = max(5, min(int(per_page or 20), 50))

    clauses = []
    params = []
    if search:
        likes = []
        for column in meta["search"]:
            likes.append("%s LIKE ? COLLATE NOCASE" % column)
            params.append("%" + search + "%")
        clauses.append("(" + " OR ".join(likes) + ")")
    where_sql = _where(clauses)
    total = count_sql(
        "SELECT COUNT(*) FROM %s%s" % (meta["base_from"], where_sql),
        params,
    )
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    if page > pages:
        page = pages
    offset = (page - 1) * per_page
    rows = get_db().execute(
        "SELECT %s FROM %s%s ORDER BY %s LIMIT ? OFFSET ?"
        % (meta["select"], meta["base_from"], where_sql, meta["order"]),
        params + [per_page, offset],
    ).fetchall()
    records = []
    for row in rows:
        data = dict(row)
        records.append(
            [ _format_inspect_value(key, data.get(key)) for key in meta["keys"] ]
        )
    return {
        "key": table_name,
        "label": meta["label"],
        "headers": meta["headers"],
        "records": records,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "search": search,
        "has_prev": page > 1,
        "has_next": page < pages,
    }
