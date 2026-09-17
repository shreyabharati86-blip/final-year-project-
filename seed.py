from werkzeug.security import generate_password_hash

from models import (
    create_company,
    create_course,
    create_job,
    create_profile,
    create_user,
    has_users,
)


def seed_if_empty():
    if has_users():
        return

    create_user(
        name="Portal Admin",
        email="admin@hirehub.com",
        password_hash=generate_password_hash("admin123"),
        role="admin",
    )

    company_user_id = create_user(
        name="Priya Sharma",
        email="hr@technova.com",
        password_hash=generate_password_hash("company123"),
        role="company",
    )
    pending_user_id = create_user(
        name="Amit Verma",
        email="hr@cloudworks.com",
        password_hash=generate_password_hash("company123"),
        role="company",
    )
    candidate_id = create_user(
        name="Rahul Mehta",
        email="rahul@gmail.com",
        password_hash=generate_password_hash("user123"),
        role="candidate",
    )

    technova_id = create_company(
        user_id=company_user_id,
        name="TechNova",
        industry="Information Technology",
        description="Product company building web and cloud tools.",
        approved=True,
    )
    create_company(
        user_id=pending_user_id,
        name="CloudWorks",
        industry="Cloud Services",
        description="Cloud consulting and internships.",
        approved=False,
    )

    create_profile(
        user_id=candidate_id,
        education="B.Tech Computer Science",
        skills="HTML, CSS, JavaScript, Python",
        experience="College projects and a 2-month web internship.",
    )

    jobs = [
        (
            "Junior Python Developer",
            "job",
            "Bengaluru",
            "4–6 LPA",
            "Python, Flask, SQL",
            "Work on APIs and internal tools with the backend team.",
        ),
        (
            "Frontend Intern",
            "internship",
            "Remote",
            "Stipend 15k/month",
            "HTML, CSS, JavaScript, Bootstrap",
            "Build UI pages and fix layout bugs on the customer portal.",
        ),
        (
            "Java Developer",
            "job",
            "Hyderabad",
            "5–7 LPA",
            "Java, SQL",
            "Join the enterprise services team. Java is required.",
        ),
        (
            "UI/UX Intern",
            "internship",
            "Pune",
            "Stipend 12k/month",
            "Figma, HTML, CSS",
            "Design screens and hand off simple HTML/CSS to developers.",
        ),
        (
            "Data Analyst",
            "job",
            "Mumbai",
            "4–5.5 LPA",
            "SQL, Python, Excel",
            "Clean data, write SQL, and build weekly reports.",
        ),
    ]
    for title, job_type, location, salary, required_skills, description in jobs:
        create_job(
            company_id=technova_id,
            title=title,
            job_type=job_type,
            location=location,
            salary=salary,
            required_skills=required_skills,
            description=description,
        )

    create_course(
        company_id=technova_id,
        skill="Java",
        title="Java for Beginners",
        description="Company course covering Java basics before the developer role.",
    )
    create_course(
        company_id=technova_id,
        skill="Flask",
        title="Flask Crash Course",
        description="Build a small API and connect it to a database.",
    )
    create_course(
        company_id=technova_id,
        skill="SQL",
        title="SQL Essentials",
        description="Select, joins, and grouping for job tasks.",
    )
