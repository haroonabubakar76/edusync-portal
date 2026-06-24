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

def calculate_grade(total: float, boundaries: list) -> tuple[str, str]:
    """Return (grade, remark) for a total score."""
    for boundary in sorted(boundaries, key=lambda x: x["min"], reverse=True):
        if total >= boundary["min"]:
            return boundary["grade"], boundary["remark"]
    return "F", "Fail"


def get_active_config(school_id: str, term: str, db: Session) -> GradingConfig:
    session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()

    config = db.query(GradingConfig).filter(
        GradingConfig.school_id == school_id,
        GradingConfig.is_active == True
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="No grading config found. Ask your principal to set it up.")
    return config


def calculate_positions(results: list[Result], db: Session):
    """Calculate class positions based on total scores for a subject/term."""
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
    term: Optional[str] = None  # defaults to active session term


class BulkScoreEntry(BaseModel):
    entries: List[ScoreEntry]


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/save")
def save_score(
    body: ScoreEntry,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save or update a single score entry. Called on auto-save."""
    school_id = current_user.school_id

    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()
    if not active_session:
        raise HTTPException(status_code=404, detail="No active academic session found.")

    term = body.term or active_session.current_term
    config = get_active_config(school_id, term, db)

    # Validate scores against config maximums
    if body.ca1_score > config.ca1_max:
        raise HTTPException(status_code=400, detail=f"CA1 score cannot exceed {config.ca1_max}")
    if body.ca2_score > config.ca2_max:
        raise HTTPException(status_code=400, detail=f"CA2 score cannot exceed {config.ca2_max}")
    if body.exam_score > config.exam_max:
        raise HTTPException(status_code=400, detail=f"Exam score cannot exceed {config.exam_max}")

    # Calculate total
    total = body.ca1_score + body.ca2_score + body.exam_score
    boundaries = json.loads(config.grade_boundaries)
    grade, remark = calculate_grade(total, boundaries)

    # Check if result already exists
    existing = db.query(Result).filter(
        Result.student_id == body.student_id,
        Result.subject_id == body.subject_id,
        Result.session_id == active_session.id,
        Result.term == term
    ).first()

    if existing:
        # Cannot edit submitted/approved results
        if existing.status in [ResultStatus.submitted, ResultStatus.approved]:
            raise HTTPException(
                status_code=403,
                detail="Result already submitted. Raise a correction request to edit."
            )
        existing.ca1_score = body.ca1_score
        existing.ca2_score = body.ca2_score
        existing.exam_score = body.exam_score
        existing.total_score = total
        existing.grade = grade
        existing.remark = remark
        existing.grading_config_id = config.id
        existing.sync_status = SyncStatus.pending
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Score updated", "result_id": existing.id, "total": total, "grade": grade}

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

    return {"message": "Score saved", "result_id": result.id, "total": total, "grade": grade}


@router.post("/submit/{subject_id}")
def submit_results(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Teacher submits all draft results for a subject. Locks them for editing."""
    school_id = current_user.school_id

    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()

    draft_results = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term,
        Result.status == ResultStatus.draft
    ).all()

    if not draft_results:
        raise HTTPException(status_code=404, detail="No draft results to submit for this subject.")

    for r in draft_results:
        r.status = ResultStatus.submitted
        r.submitted_at = datetime.utcnow()

    # Calculate positions after submission
    all_results = db.query(Result).filter(
        Result.subject_id == subject_id,
        Result.session_id == active_session.id,
        Result.term == active_session.current_term,
        Result.status == ResultStatus.submitted
    ).all()
    calculate_positions(all_results, db)

    # Audit
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
    """Principal approves submitted results for a subject."""
    school_id = current_user.school_id

    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active == True
    ).first()

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


@router.get("/student/{student_id}")
def get_student_results(
    student_id: str,
    term: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all results for a student — used for result card generation."""
    active_session = db.query(AcademicSession).filter(
        AcademicSession.school_id == current_user.school_id,
        AcademicSession.is_active == True
    ).first()

    query = db.query(Result).filter(
        Result.student_id == student_id,
        Result.session_id == active_session.id
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
