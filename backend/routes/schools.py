from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import (School, Section, Class, Subject, AcademicSession,
                    GradingConfig, Teacher, User, UserRole)
from auth import get_current_user, require_role
from datetime import datetime
import json

router = APIRouter(prefix="/schools", tags=["schools"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SchoolCreate(BaseModel):
    id: str                          # e.g. "SCH001"
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class SectionCreate(BaseModel):
    name: str                        # "JSS" or "SSS"


class ClassCreate(BaseModel):
    section_id: int
    name: str                        # "JSS1A", "SSS2B"


class SubjectCreate(BaseModel):
    class_id: int
    name: str
    teacher_id: Optional[int] = None


class SessionCreate(BaseModel):
    name: str                        # "2024/2025"
    current_term: str = "first"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class GradingConfigCreate(BaseModel):
    term: str                        # "first", "second", "third"
    ca1_max: int = 20
    ca2_max: int = 20
    exam_max: int = 60
    pass_mark: int = 40
    grade_boundaries: Optional[str] = None  # JSON string


# ─── School ───────────────────────────────────────────────────────────────────

@router.post("/")
def create_school(
    body: SchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.super_admin))
):
    existing = db.query(School).filter(School.id == body.id.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail="School ID already exists.")

    school = School(
        id=body.id.upper(),
        name=body.name.strip(),
        address=body.address,
        phone=body.phone,
        email=body.email,
        is_active=True,
        subscription_status="active"
    )
    db.add(school)
    db.commit()
    db.refresh(school)
    return {"message": "School created", "school_id": school.id, "name": school.name}


@router.get("/")
def list_schools(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.super_admin))
):
    schools = db.query(School).all()
    return [{"id": s.id, "name": s.name, "is_active": s.is_active,
             "subscription_status": s.subscription_status} for s in schools]


@router.get("/me")
def get_my_school(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns the school profile for the logged-in user's school."""
    school = db.query(School).filter(School.id == current_user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    return {
        "id": school.id,
        "name": school.name,
        "address": school.address,
        "phone": school.phone,
        "email": school.email,
        "is_active": school.is_active,
        "subscription_status": school.subscription_status
    }


@router.patch("/{school_id}/suspend")
def suspend_school(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.super_admin))
):
    school = db.query(School).filter(School.id == school_id.upper()).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    school.subscription_status = "suspended"
    school.is_active = False
    db.commit()
    return {"message": f"{school.name} has been suspended."}


@router.patch("/{school_id}/activate")
def activate_school(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.super_admin))
):
    school = db.query(School).filter(School.id == school_id.upper()).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    school.subscription_status = "active"
    school.is_active = True
    db.commit()
    return {"message": f"{school.name} has been activated."}


# ─── Sections ─────────────────────────────────────────────────────────────────

@router.post("/{school_id}/sections")
def create_section(
    school_id: str,
    body: SectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    school = db.query(School).filter(School.id == school_id.upper()).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    section = Section(school_id=school_id.upper(), name=body.name.upper())
    db.add(section)
    db.commit()
    db.refresh(section)
    return {"message": "Section created", "section_id": section.id, "name": section.name}


@router.get("/{school_id}/sections")
def list_sections(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sections = db.query(Section).filter(Section.school_id == school_id.upper()).all()
    return [{"id": s.id, "name": s.name} for s in sections]


# ─── Classes ──────────────────────────────────────────────────────────────────

@router.post("/{school_id}/classes")
def create_class(
    school_id: str,
    body: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    section = db.query(Section).filter(
        Section.id == body.section_id,
        Section.school_id == school_id.upper()
    ).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")

    class_ = Class(section_id=body.section_id, name=body.name.upper())
    db.add(class_)
    db.commit()
    db.refresh(class_)
    return {"message": "Class created", "class_id": class_.id, "name": class_.name}


@router.get("/{school_id}/classes")
def list_classes(
    school_id: str,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sections = db.query(Section).filter(Section.school_id == school_id.upper()).all()
    section_ids = [s.id for s in sections]

    query = db.query(Class).filter(Class.section_id.in_(section_ids))
    if section_id:
        query = query.filter(Class.section_id == section_id)

    classes = query.order_by(Class.name).all()
    return [{"id": c.id, "name": c.name, "section_id": c.section_id} for c in classes]


# ─── Subjects ─────────────────────────────────────────────────────────────────

@router.post("/{school_id}/subjects")
def create_subject(
    school_id: str,
    body: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    class_ = db.query(Class).filter(Class.id == body.class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found.")

    subject = Subject(
        class_id=body.class_id,
        name=body.name.strip(),
        teacher_id=body.teacher_id
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return {"message": "Subject created", "subject_id": subject.id, "name": subject.name}


@router.get("/{school_id}/subjects")
def list_subjects(
    school_id: str,
    class_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Subject)
    if class_id:
        query = query.filter(Subject.class_id == class_id)

    subjects = query.order_by(Subject.name).all()
    return [{"id": s.id, "name": s.name, "class_id": s.class_id,
             "teacher_id": s.teacher_id} for s in subjects]


@router.patch("/{school_id}/subjects/{subject_id}/assign")
def assign_teacher(
    school_id: str,
    subject_id: int,
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.school_id == school_id.upper()
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found in this school.")

    subject.teacher_id = teacher_id
    db.commit()
    return {"message": "Teacher assigned to subject."}


# ─── Academic Sessions ────────────────────────────────────────────────────────

@router.post("/{school_id}/sessions")
def create_session(
    school_id: str,
    body: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    # Deactivate current active session first
    db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id.upper(),
        AcademicSession.is_active == True
    ).update({"is_active": False})

    start = datetime.strptime(body.start_date, "%Y-%m-%d") if body.start_date else None
    end = datetime.strptime(body.end_date, "%Y-%m-%d") if body.end_date else None

    session = AcademicSession(
        school_id=school_id.upper(),
        name=body.name,
        current_term=body.current_term,
        is_active=True,
        start_date=start,
        end_date=end
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"message": "Academic session created", "session_id": session.id, "name": session.name}


@router.patch("/{school_id}/sessions/{session_id}/term")
def update_current_term(
    school_id: str,
    session_id: int,
    term: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    if term not in ["first", "second", "third"]:
        raise HTTPException(status_code=400, detail="Term must be 'first', 'second', or 'third'.")

    session = db.query(AcademicSession).filter(
        AcademicSession.id == session_id,
        AcademicSession.school_id == school_id.upper()
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.current_term = term
    db.commit()
    return {"message": f"Current term updated to {term}."}


@router.get("/{school_id}/sessions")
def list_sessions(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sessions = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id.upper()
    ).order_by(AcademicSession.created_at.desc()).all()
    return [{"id": s.id, "name": s.name, "current_term": s.current_term,
             "is_active": s.is_active} for s in sessions]


# ─── Grading Config ───────────────────────────────────────────────────────────

@router.post("/{school_id}/grading-config")
def set_grading_config(
    school_id: str,
    body: GradingConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    if body.ca1_max + body.ca2_max + body.exam_max != 100:
        raise HTTPException(status_code=400, detail="CA1 + CA2 + Exam must total 100.")

    # Deactivate old config
    db.query(GradingConfig).filter(
        GradingConfig.school_id == school_id.upper(),
        GradingConfig.is_active == True
    ).update({"is_active": False})

    boundaries = body.grade_boundaries or json.dumps([
        {"min": 70, "max": 100, "grade": "A", "remark": "Excellent"},
        {"min": 60, "max": 69, "grade": "B", "remark": "Good"},
        {"min": 50, "max": 59, "grade": "C", "remark": "Average"},
        {"min": 40, "max": 49, "grade": "D", "remark": "Below Average"},
        {"min": 0,  "max": 39, "grade": "F", "remark": "Fail"}
    ])

    config = GradingConfig(
        school_id=school_id.upper(),
        term=body.term,
        ca1_max=body.ca1_max,
        ca2_max=body.ca2_max,
        exam_max=body.exam_max,
        pass_mark=body.pass_mark,
        grade_boundaries=boundaries,
        is_active=True
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"message": "Grading config saved.", "config_id": config.id}


@router.get("/{school_id}/grading-config")
def get_grading_config(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = db.query(GradingConfig).filter(
        GradingConfig.school_id == school_id.upper(),
        GradingConfig.is_active == True
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="No grading config set for this school.")

    return {
        "id": config.id,
        "ca1_max": config.ca1_max,
        "ca2_max": config.ca2_max,
        "exam_max": config.exam_max,
        "pass_mark": config.pass_mark,
        "grade_boundaries": json.loads(config.grade_boundaries)
    }
