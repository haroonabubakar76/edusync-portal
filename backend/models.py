from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text,
    ForeignKey, DateTime, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    school_admin = "school_admin"
    teacher = "teacher"

class StudentStatus(str, enum.Enum):
    active = "active"
    promoted = "promoted"
    repeated = "repeated"
    transferred = "transferred"
    inactive = "inactive"

class ResultStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"

class SyncStatus(str, enum.Enum):
    pending = "pending"
    synced = "synced"
    failed = "failed"


# ─── School ───────────────────────────────────────────────────────────────────

class School(Base):
    __tablename__ = "schools"

    id = Column(String, primary_key=True)           # e.g. "SCH001"
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    logo_url = Column(String)                        # URL only, never stored on device
    is_active = Column(Boolean, default=True)
    subscription_status = Column(String, default="active")  # active, grace, readonly, suspended
    subscription_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sections = relationship("Section", back_populates="school", cascade="all, delete-orphan")
    teachers = relationship("Teacher", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    grading_configs = relationship("GradingConfig", back_populates="school", cascade="all, delete-orphan")
    sessions = relationship("AcademicSession", back_populates="school", cascade="all, delete-orphan")


# ─── Grading Config ───────────────────────────────────────────────────────────

class GradingConfig(Base):
    __tablename__ = "grading_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=True)
    term = Column(String, nullable=False)           # "first", "second", "third"
    ca1_max = Column(Integer, default=20)
    ca2_max = Column(Integer, default=20)
    exam_max = Column(Integer, default=60)
    # Grade boundaries stored as JSON string: [{"min":70,"max":100,"grade":"A","remark":"Excellent"}, ...]
    grade_boundaries = Column(Text, default='[{"min":70,"max":100,"grade":"A","remark":"Excellent"},{"min":60,"max":69,"grade":"B","remark":"Good"},{"min":50,"max":59,"grade":"C","remark":"Average"},{"min":40,"max":49,"grade":"D","remark":"Below Average"},{"min":0,"max":39,"grade":"F","remark":"Fail"}]')
    pass_mark = Column(Integer, default=40)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    school = relationship("School", back_populates="grading_configs")


# ─── Academic Session & Term ───────────────────────────────────────────────────

class AcademicSession(Base):
    __tablename__ = "academic_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)           # e.g. "2024/2025"
    current_term = Column(String, default="first")  # first, second, third
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    school = relationship("School", back_populates="sessions")


# ─── Section ──────────────────────────────────────────────────────────────────

class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)           # "JSS" or "SSS"
    created_at = Column(DateTime, default=datetime.utcnow)

    school = relationship("School", back_populates="sections")
    classes = relationship("Class", back_populates="section", cascade="all, delete-orphan")


# ─── Class ────────────────────────────────────────────────────────────────────

class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    name = Column(String, nullable=False)           # "JSS1A", "SSS2B"
    created_at = Column(DateTime, default=datetime.utcnow)

    section = relationship("Section", back_populates="classes")
    subjects = relationship("Subject", back_populates="class_", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="class_")


# ─── Subject ──────────────────────────────────────────────────────────────────

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    name = Column(String, nullable=False)           # "Mathematics", "English Language"
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="subjects")
    teacher = relationship("Teacher", back_populates="subjects")
    results = relationship("Result", back_populates="subject")


# ─── User (base for all login accounts) ──────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=True)  # null for super admin
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# ─── Teacher ──────────────────────────────────────────────────────────────────

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    staff_id = Column(String)                       # optional staff number
    created_at = Column(DateTime, default=datetime.utcnow)

    school = relationship("School", back_populates="teachers")
    subjects = relationship("Subject", back_populates="teacher")


# ─── Student ──────────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True)           # SCH/2023/JSS1/001 — never changes
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    full_name = Column(String, nullable=False)
    gender = Column(String)                         # "M" or "F"
    date_of_birth = Column(DateTime, nullable=True)
    admission_year = Column(Integer, nullable=False)
    parent_name = Column(String)
    parent_phone = Column(String)
    parent_whatsapp = Column(String)
    parent_consent = Column(Boolean, default=False) # consent to receive notifications
    status = Column(SAEnum(StudentStatus), default=StudentStatus.active)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school = relationship("School", back_populates="students")
    class_ = relationship("Class", back_populates="students")
    results = relationship("Result", back_populates="student")


# ─── Result ───────────────────────────────────────────────────────────────────

class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=False)
    term = Column(String, nullable=False)           # "first", "second", "third"

    ca1_score = Column(Float, default=0)
    ca2_score = Column(Float, default=0)
    exam_score = Column(Float, default=0)
    total_score = Column(Float, default=0)          # auto-calculated
    grade = Column(String)                          # auto-calculated
    remark = Column(String)                         # auto-calculated
    position = Column(Integer, nullable=True)       # calculated after all results submitted

    # Grading config snapshot — preserved even if school changes config later
    grading_config_id = Column(Integer, ForeignKey("grading_configs.id"), nullable=True)

    status = Column(SAEnum(ResultStatus), default=ResultStatus.draft)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    sync_status = Column(SAEnum(SyncStatus), default=SyncStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="results")
    subject = relationship("Subject", back_populates="results")


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)         # "result_submitted", "result_approved", etc.
    entity_type = Column(String)                    # "result", "student", "user"
    entity_id = Column(String)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Sync Queue ───────────────────────────────────────────────────────────────

class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=False)
    table_name = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    operation = Column(String, nullable=False)      # "insert", "update"
    payload = Column(Text, nullable=False)          # JSON string
    status = Column(SAEnum(SyncStatus), default=SyncStatus.pending)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)
