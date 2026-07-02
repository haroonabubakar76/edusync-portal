from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import (Result, Student, Subject, GradingConfig, AcademicSession,
                    User, UserRole, ResultStatus, SyncStatus, AuditLog)
from auth import get_current_user, require_role
from datetime import datetime
import json

router = APIRouter(prefix="/results", tags=["results"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def calculate_grade(total: float, boundaries: list) -> tuple:
    for boundary in sorted(boundaries, key=lambda x: x["min"], reverse=True):
        if total >= boundary["min"]:
            return boundary["grade"], boundary["remark"]
    return "F", "Fail"


def get_active_session(school_id: str, db: Session) -> AcademicSession:
    session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()
    if not session:
        # fallback — get most recent session
        session = db.query(AcademicSession).filter(
            AcademicSession.school_id == school_id
        ).order_by(AcademicSession.id.desc()).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="No academic session found. Ask your principal to create one."
        )
    return session


def get_active_config(school_id: str, db: Session) -> GradingConfig:
    config = db.query(GradingConfig).filter(
        GradingConfig.school_id == school_id,
        GradingConfig.is_active == True
    ).first()
    if not config:
        # Create default config automatically
        config = GradingConfig(
            school_id=school_id,
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
        db.commit()
        db.refresh(config)
    return config


def calculate_positions(results, db: Session):
    sorted_results = sorted(results, key=lambda r: r.total_score, reverse=True)
    for pos, result in enumerate(sorted_results, start=1):
        result.position = pos
    db.commit()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ScoreEntry(BaseModel):
    student_id: str
    subject_id: int
    ca1_score: float
    ca2_score: float
    exam_score: float
    term: Optional[str] = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/save")
def save_score(
    body: ScoreEntry,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = current_user.school_id
    active_session = get_active_session(school_id, db)
    config = get_active_config(school_id, db)

    term = body.term or active_session.current_term

    # Validate scores
    if body.ca1_score < 0 or body.ca1_score > config.ca1_max:
        raise HTTPException(status_code=400, detail=f"CA1 score must be between 0 and {config.ca1_max}")
    if body.ca2_score < 0 or body.ca2_score > config.ca2_max:
        raise HTTPException(status_code=400, detail=f"CA2 score must be between 0 and {config.ca2_max}")
    if body.exam_score < 0 or body.exam_score > config.exam_max:
        raise HTTPException(status_code=400, detail=f"Exam score must be between 0 and {config.exam_max}")

    total = body.ca1_score + body.ca2_score + body.exam_score
    boundaries = json.loads(config.grade_boundaries)
    grade, remark = calculate_grade(total, boundaries)

    # Update existing or create new
    existing = db.query(Result).filter(
        Result.student_id == body.student_id,
        Result.subject_id == body.subject_id,
        Result.session_id == active_session.id,
        Result.term == term
    ).first()

    if existing:
        if existing.status in [ResultStatus.submitted, ResultStatus.approved]:
            raise HTTPException(
                status_code=403,
                detail="Result already submitted. Request a correction to edit."
            )
        existing.ca1_score    = body.ca1_score
        existing.ca2_score    = body.ca2_score
        existing.exam_score   = body.exam_score
        existing.total_score  = total
        existing.grade        = grade
        existing.remark       = remark
        existing.grading_config_id = config.id
        existing.sync_status  = SyncStatus.pending
        existing.updated_at   = datetime.utcnow()
        db.commit()
        return {"message": "Score updated", "result_id": existing.id, "total": total, "grade": grade, "remark": remark}

    result = Result(
        student_id=body.student_id,
        subject_id=body.subject_id,
        session_id=active_session.id,
        term=term,
        ca1_score=body.ca1_score,
        ca2_score=body.ca2_score,
        exam_score=body.exam_score,
        total_score=total,
        grade=grade,
        remark=remark,
        grading_config_id=config.id,
        status=ResultStatus.draft,
        sync_status=SyncStatus.pending
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    return {"message": "Score saved", "result_id": result.id, "total": total, "grade": grade, "remark": remark}


@router.post("/submit/{subject_id}")
def submit_results(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = current_user.school_id
    active_session = get_active_session(school_id, db)

    draft_results = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term,
        Result.status.in_([ResultStatus.draft, ResultStatus.rejected])
    ).all()

    if not draft_results:
        raise HTTPException(status_code=404, detail="No draft results found for this subject.")

    for r in draft_results:
        r.status = ResultStatus.submitted
        r.submitted_at = datetime.utcnow()

    # Calculate positions
    all_submitted = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term
    ).all()
    calculate_positions(all_submitted, db)

    log = AuditLog(
        school_id=school_id,
        user_id=current_user.id,
        action="results_submitted",
        entity_type="subject",
        entity_id=str(subject_id),
        new_value=f"{len(draft_results)} results submitted"
    )
    db.add(log)
    db.commit()

    return {"message": f"{len(draft_results)} results submitted for approval."}


@router.post("/approve/{subject_id}")
def approve_results(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    school_id = current_user.school_id
    active_session = get_active_session(school_id, db)

    submitted = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term,
        Result.status == ResultStatus.submitted
    ).all()

    if not submitted:
        raise HTTPException(status_code=404, detail="No submitted results to approve.")

    for r in submitted:
        r.status = ResultStatus.approved
        r.approved_at = datetime.utcnow()
        r.approved_by = current_user.id

    log = AuditLog(
        school_id=school_id,
        user_id=current_user.id,
        action="results_approved",
        entity_type="subject",
        entity_id=str(subject_id),
        new_value=f"{len(submitted)} results approved"
    )
    db.add(log)
    db.commit()

    return {"message": f"{len(submitted)} results approved."}


@router.get("/student/{student_id:path}")
def get_student_results(
    student_id: str,
    term: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all results for a student — result card generation."""

    # Get school_id from student record directly — more reliable
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    school_id = student.school_id

    # Get active session — fallback to most recent
    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()

    if not active_session:
        active_session = db.query(AcademicSession).filter(
            AcademicSession.school_id == school_id
        ).order_by(AcademicSession.id.desc()).first()

    if not active_session:
        return []

    # Get results — no session filter if results exist across sessions
    query = db.query(Result).filter(
        Result.student_id == student_id
    )

    if term:
        query = query.filter(Result.term == term)

    results = query.all()

    return [
        {
            "id": r.id,
            "subject_id": r.subject_id,
            "term": r.term,
            "ca1_score": r.ca1_score,
            "ca2_score": r.ca2_score,
            "exam_score": r.exam_score,
            "total_score": r.total_score,
            "grade": r.grade,
            "remark": r.remark,
            "position": r.position,
            "status": r.status.value
        }
        for r in results
    ]


@router.get("/stats/{school_id}")
def get_result_stats(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get result statistics for dashboard stats."""
    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()

    if not active_session:
        return {"draft": 0, "submitted": 0, "approved": 0, "rejected": 0}

    draft     = db.query(Result).filter(Result.session_id == active_session.id, Result.status == ResultStatus.draft).count()
    submitted = db.query(Result).filter(Result.session_id == active_session.id, Result.status == ResultStatus.submitted).count()
    approved  = db.query(Result).filter(Result.session_id == active_session.id, Result.status == ResultStatus.approved).count()
    rejected  = db.query(Result).filter(Result.session_id == active_session.id, Result.status == ResultStatus.rejected).count()

    return {"draft": draft, "submitted": submitted, "approved": approved, "rejected": rejected}


@router.post("/reject/{subject_id}")
def reject_results(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.school_admin, UserRole.super_admin))
):
    """Principal rejects submitted results — teacher can edit and resubmit."""
    school_id = current_user.school_id
    active_session = get_active_session(school_id, db)

    submitted = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term,
        Result.status == ResultStatus.submitted
    ).all()

    if not submitted:
        raise HTTPException(status_code=404, detail="No submitted results to reject.")

    for r in submitted:
        r.status = ResultStatus.rejected

    log = AuditLog(
        school_id=school_id,
        user_id=current_user.id,
        action="results_rejected",
        entity_type="subject",
        entity_id=str(subject_id),
        new_value=f"{len(submitted)} results rejected"
    )
    db.add(log)
    db.commit()

    return {"message": f"{len(submitted)} results rejected. Teacher can now edit and resubmit."}


@router.get("/class-positions/{class_id}")
def get_class_positions(
    class_id: int,
    term: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate overall class positions based on average across all subjects."""
    school_id = current_user.school_id
    active_session = get_active_session(school_id, db)
    t = term or active_session.current_term

    # Get all students in class
    students = db.query(Student).filter(
        Student.class_id == class_id,
        Student.school_id == school_id
    ).all()

    positions = []
    for student in students:
        results = db.query(Result).filter(
            Result.student_id == student.id,
            Result.term == t,
            Result.status.in_([ResultStatus.submitted, ResultStatus.approved])
        ).all()

        if not results:
            continue

        total    = sum(r.total_score for r in results)
        average  = total / len(results)
        positions.append({
            "student_id":   student.id,
            "student_name": student.full_name,
            "total_score":  total,
            "average":      round(average, 1),
            "subjects":     len(results)
        })

    # Sort by average descending and assign positions
    positions.sort(key=lambda x: x["average"], reverse=True)
    for i, p in enumerate(positions, start=1):
        p["position"] = i

    return positions
