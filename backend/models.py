from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid

# Import Base from database module to ensure all models use the same Base
from database import Base


# ===== SQLAlchemy DB Models =====
class UserDB(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionDB(Base):
    __tablename__ = "questions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(String)
    category = Column(String, index=True)
    options = Column(JSON)  # List of {"id": str, "text": str, "is_correct": bool}
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrafficSignDB(Base):
    __tablename__ = "traffic_signs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    number = Column(String, unique=True)
    name = Column(String)
    description = Column(String)
    image_url = Column(String, nullable=True)
    category = Column(String)


class ExamSessionDB(Base):
    __tablename__ = "exam_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    status = Column(String, default="in_progress")  # in_progress, completed
    answers = Column(JSON, default={})  # {question_id: selected_option_id}
    score = Column(Integer, nullable=True)
    passed = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ===== Pydantic Models =====
class QuestionOption(BaseModel):
    id: str
    text: str
    is_correct: bool


class QuestionCreate(BaseModel):
    text: str
    category: str
    options: List[QuestionOption]
    explanation: Optional[str] = None


class Question(QuestionCreate):
    id: str
    created_at: datetime


class TrafficSignCreate(BaseModel):
    number: str
    name: str
    description: str
    image_url: Optional[str] = None
    category: str


class TrafficSign(TrafficSignCreate):
    id: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserInDB(UserCreate):
    id: str


class User(BaseModel):
    id: str
    email: str


class ExamSession(BaseModel):
    id: str
    user_id: str
    status: str
    answers: dict
    score: Optional[int] = None
    passed: Optional[bool] = None
    created_at: datetime


class SubmitAnswerRequest(BaseModel):
    question_id: str
    selected_option_id: str


class ExamResult(BaseModel):
    id: str
    user_id: str
    status: str
    score: int
    passed: bool
    answers: dict
    created_at: datetime
    completed_at: datetime


class TrainingAnswerRequest(BaseModel):
    question_id: str
    selected_option_id: str


class TrainingResponse(BaseModel):
    is_correct: bool
    explanation: Optional[str] = None
    correct_option_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
