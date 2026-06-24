from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import User
from auth import verify_password, create_token, get_current_user
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    full_name: str
    role: str
    school_id: Optional[str]


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Support login by email or phone
    user = db.query(User).filter(
        (User.email == body.email.lower()) | (User.phone == body.email)
    ).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact your administrator."
        )

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_token({"sub": str(user.id), "role": user.role, "school_id": user.school_id})

    return LoginResponse(
        token=token,
        user_id=user.id,
        full_name=user.full_name,
        role=user.role.value,
        school_id=user.school_id
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "school_id": current_user.school_id,
        "is_active": current_user.is_active
    }
