"""
Run this once to bootstrap EduSync Portal with:
  - Super Admin account
  - A test school
  - JSS and SSS sections
  - Sample classes and subjects
  - A school admin (principal) account
  - A teacher account
  - Active academic session with grading config

Usage:
    python seed.py
"""

from database import SessionLocal, create_tables
from models import (User, UserRole, School, Section, Class, Subject,
                    Teacher, AcademicSession, GradingConfig)
from auth import hash_password
import json

def seed():
    create_tables()
    db = SessionLocal()

    print("🌱 Seeding EduSync Portal...")

    # ── Super Admin ──────────────────────────────────────────────────────────
    existing_admin = db.query(User).filter(User.email == "admin@edusync.ng").first()
    if not existing_admin:
        super_admin = User(
            school_id=None,
            full_name="EduSync Super Admin",
            email="admin@edusync.ng",
            password_hash=hash_password("Admin@1234"),
            role=UserRole.super_admin,
            is_active=True
        )
        db.add(super_admin)
        db.flush()
        print(f"  ✅ Super Admin created — email: admin@edusync.ng | password: Admin@1234")
    else:
        print("  ⏭  Super Admin already exists")

    # ── Test School ───────────────────────────────────────────────────────────
    school = db.query(School).filter(School.id == "SCH001").first()
    if not school:
        school = School(
            id="SCH001",
            name="Bright Future Secondary School",
            address="No. 12 Ibrahim Badamasi Way, Minna, Niger State",
            phone="08012345678",
            email="brightfuture@school.ng",
            is_active=True,
            subscription_status="active"
        )
        db.add(school)
        db.flush()
        print(f"  ✅ School created — ID: SCH001 | {school.name}")
    else:
        print("  ⏭  School already exists")

    # ── Sections ──────────────────────────────────────────────────────────────
    jss = db.query(Section).filter(Section.school_id == "SCH001", Section.name == "JSS").first()
    if not jss:
        jss = Section(school_id="SCH001", name="JSS")
        db.add(jss)
        db.flush()
        print("  ✅ Section created — JSS")

    sss = db.query(Section).filter(Section.school_id == "SCH001", Section.name == "SSS").first()
    if not sss:
        sss = Section(school_id="SCH001", name="SSS")
        db.add(sss)
        db.flush()
        print("  ✅ Section created — SSS")

    # ── Classes ───────────────────────────────────────────────────────────────
    class_names = ["JSS1A", "JSS2A", "JSS3A"]
    classes = {}
    for name in class_names:
        cls = db.query(Class).filter(Class.section_id == jss.id, Class.name == name).first()
        if not cls:
            cls = Class(section_id=jss.id, name=name)
            db.add(cls)
            db.flush()
            print(f"  ✅ Class created — {name}")
        classes[name] = cls

    # ── Principal (School Admin) ───────────────────────────────────────────────
    principal_user = db.query(User).filter(User.email == "principal@brightfuture.ng").first()
    if not principal_user:
        principal_user = User(
            school_id="SCH001",
            full_name="Mr. Abubakar Suleiman",
            email="principal@brightfuture.ng",
            phone="08098765432",
            password_hash=hash_password("Principal@1234"),
            role=UserRole.school_admin,
            is_active=True
        )
        db.add(principal_user)
        db.flush()
        print(f"  ✅ Principal created — email: principal@brightfuture.ng | password: Principal@1234")

    # ── Teacher ───────────────────────────────────────────────────────────────
    teacher_user = db.query(User).filter(User.email == "teacher@brightfuture.ng").first()
    if not teacher_user:
        teacher_user = User(
            school_id="SCH001",
            full_name="Mrs. Fatima Bello",
            email="teacher@brightfuture.ng",
            phone="08055556666",
            password_hash=hash_password("Teacher@1234"),
            role=UserRole.teacher,
            is_active=True
        )
        db.add(teacher_user)
        db.flush()

        teacher = Teacher(user_id=teacher_user.id, school_id="SCH001", staff_id="TCH001")
        db.add(teacher)
        db.flush()
        print(f"  ✅ Teacher created — email: teacher@brightfuture.ng | password: Teacher@1234")
    else:
        teacher = db.query(Teacher).filter(Teacher.user_id == teacher_user.id).first()

    # ── Subjects for JSS1A ────────────────────────────────────────────────────
    subject_names = [
        "Mathematics", "English Language", "Basic Science",
        "Social Studies", "Civic Education", "Agricultural Science"
    ]
    jss1a = classes.get("JSS1A")
    for subj_name in subject_names:
        subj = db.query(Subject).filter(
            Subject.class_id == jss1a.id, Subject.name == subj_name
        ).first()
        if not subj:
            subj = Subject(
                class_id=jss1a.id,
                name=subj_name,
                teacher_id=teacher.id if teacher else None
            )
            db.add(subj)
    db.flush()
    print(f"  ✅ Subjects created for JSS1A")

    # ── Academic Session ──────────────────────────────────────────────────────
    session = db.query(AcademicSession).filter(
        AcademicSession.school_id == "SCH001",
        AcademicSession.name == "2024/2025"
    ).first()
    if not session:
        session = AcademicSession(
            school_id="SCH001",
            name="2024/2025",
            current_term="first",
            is_active=True
        )
        db.add(session)
        db.flush()
        print("  ✅ Academic session created — 2024/2025 | First Term")

    # ── Grading Config ────────────────────────────────────────────────────────
    config = db.query(GradingConfig).filter(
        GradingConfig.school_id == "SCH001",
        GradingConfig.is_active == True
    ).first()
    if not config:
        config = GradingConfig(
            school_id="SCH001",
            term="first",
            ca1_max=20,
            ca2_max=20,
            exam_max=60,
            pass_mark=40,
            grade_boundaries=json.dumps([
                {"min": 70, "max": 100, "grade": "A", "remark": "Excellent"},
                {"min": 60, "max": 69,  "grade": "B", "remark": "Good"},
                {"min": 50, "max": 59,  "grade": "C", "remark": "Average"},
                {"min": 40, "max": 49,  "grade": "D", "remark": "Below Average"},
                {"min": 0,  "max": 39,  "grade": "F", "remark": "Fail"}
            ]),
            is_active=True
        )
        db.add(config)
        print("  ✅ Grading config set — CA1(20) + CA2(20) + Exam(60) = 100")

    db.commit()
    db.close()

    print("\n🎉 Seed complete! EduSync Portal is ready.")
    print("\n── Login Credentials ───────────────────────────────")
    print("  Super Admin  → admin@edusync.ng        | Admin@1234")
    print("  Principal    → principal@brightfuture.ng | Principal@1234")
    print("  Teacher      → teacher@brightfuture.ng   | Teacher@1234")
    print("────────────────────────────────────────────────────")
    print("\n  Run the server: uvicorn main:app --reload")
    print("  API Docs:       http://localhost:8000/docs\n")


if __name__ == "__main__":
    seed()
