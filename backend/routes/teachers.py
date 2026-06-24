from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import User, Teacher, UserRole
from auth import get_current_user, require_role, hash_password
from datetime import datetime

router = APIRouter(prefix="/teachers", tags=["teachers"])


class TeacherCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    password: str
    staff_id: Optional[str] = None


@router.post("/")
def create_teacher(
    body: TeacherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    school_id = current_user.school_id

    user = User(
        school_id=school_id,
        full_name=body.full_name.strip(),
        email=body.email.lower().strip(),
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=UserRole.teacher,
        is_active=True
    )
    db.add(user)
    db.flush()  # get user.id without full commit

    teacher = Teacher(
        user_id=user.id,
        school_id=school_id,
        staff_id=body.staff_id
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    return {
        "message": "Teacher account created.",
        "teacher_id": teacher.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email
    }


@router.get("/")
def list_teachers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    teachers = db.query(Teacher).filter(
        Teacher.school_id == current_user.school_id
    ).all()

    result = []
    for t in teachers:
        user = db.query(User).filter(User.id == t.user_id).first()
        result.append({
            "teacher_id": t.id,
            "user_id": t.user_id,
            "full_name": user.full_name if user else "Unknown",
            "email": user.email if user else "",
            "is_active": user.is_active if user else False,
            "staff_id": t.staff_id
        })
    return result


@router.patch("/{teacher_id}/deactivate")
def deactivate_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.school_id == current_user.school_id
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    user = db.query(User).filter(User.id == teacher.user_id).first()
    if user:
        user.is_active = False
        db.commit()

    return {"message": "Teacher account deactivated. All data and assignments preserved."}
