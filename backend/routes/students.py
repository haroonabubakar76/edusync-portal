from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Student, Class, School, User, UserRole, StudentStatus, AuditLog
from auth import get_current_user, require_role
from datetime import datetime

router = APIRouter(prefix="/students", tags=["students"])


class StudentCreate(BaseModel):
    full_name: str
    gender: str
    class_id: int
    admission_year: int
    date_of_birth: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_whatsapp: Optional[str] = None
    parent_consent: bool = False


def generate_student_id(school_id: str, admission_year: int, class_name: str, db: Session) -> str:
    """Generate unique student ID: SCH001/2024/JSS1/001"""
    # Normalise class name — remove spaces
    class_code = class_name.replace(" ", "").upper()[:4]

    # Count existing students with same school + year + class prefix
    prefix = f"{school_id}/{admission_year}/{class_code}/"
    existing = db.query(Student).filter(Student.id.like(f"{prefix}%")).count()
    sequence = str(existing + 1).zfill(3)

    return f"{prefix}{sequence}"


@router.post("/")
def register_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    class_ = db.query(Class).filter(Class.id == body.class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    school_id = current_user.school_id
    student_id = generate_student_id(school_id, body.admission_year, class_.name, db)

    dob = None
    if body.date_of_birth:
        try:
            dob = datetime.strptime(body.date_of_birth, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    student = Student(
        id=student_id,
        school_id=school_id,
        class_id=body.class_id,
        full_name=body.full_name.strip(),
        gender=body.gender.upper(),
        date_of_birth=dob,
        admission_year=body.admission_year,
        parent_name=body.parent_name,
        parent_phone=body.parent_phone,
        parent_whatsapp=body.parent_whatsapp,
        parent_consent=body.parent_consent,
        status=StudentStatus.active
    )
    db.add(student)

    # Audit log
    log = AuditLog(
        school_id=school_id,
        user_id=current_user.id,
        action="student_registered",
        entity_type="student",
        entity_id=student_id,
        new_value=body.full_name
    )
    db.add(log)
    db.commit()
    db.refresh(student)

    return {"message": "Student registered", "student_id": student_id, "student": {
        "id": student.id,
        "full_name": student.full_name,
        "class_id": student.class_id,
        "status": student.status.value
    }}


@router.get("/")
def list_students(
    class_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Student).filter(
        Student.school_id == current_user.school_id,
        Student.status == StudentStatus.active
    )
    if class_id:
        query = query.filter(Student.class_id == class_id)

    students = query.order_by(Student.full_name).all()
    return [{"id": s.id, "full_name": s.full_name, "gender": s.gender,
             "class_id": s.class_id, "status": s.status.value} for s in students]


@router.get("/{student_id}")
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.school_id == current_user.school_id
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "id": student.id,
        "full_name": student.full_name,
        "gender": student.gender,
        "class_id": student.class_id,
        "admission_year": student.admission_year,
        "parent_name": student.parent_name,
        "parent_phone": student.parent_phone,
        "parent_consent": student.parent_consent,
        "status": student.status.value,
        "created_at": student.created_at.isoformat()
    }
