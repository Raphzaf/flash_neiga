from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid

# Helpers
def get_utc_now():
    return datetime.now(timezone.utc)

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    hashed_password: str
    created_at: datetime = Field(default_factory=get_utc_now)
    role: str = "student" # student, admin

class User(UserBase):
    id: str = Field(alias="_id")
    role: str

# Question Models
class QuestionOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    is_correct: bool

class QuestionBase(BaseModel):
    text: str
    category: str
    image_url: Optional[str] = None
    options: List[QuestionOption]
    explanation: str

class QuestionCreate(QuestionBase):
    pass

class Question(QuestionBase):
    id: str = Field(alias="_id")
    created_at: datetime

# Traffic Sign Models
class TrafficSignBase(BaseModel):
    name: str
    category: str
    description: str
    image_url: str

class TrafficSignCreate(TrafficSignBase):
    pass

class TrafficSign(TrafficSignBase):
    id: str = Field(alias="_id")

# Exam Models
class ExamRequest(BaseModel):
    pass # Just triggers creation

class ExamQuestion(BaseModel):
    question_id: str
    text: str
    category: str
    image_url: Optional[str]
    options: List[QuestionOption] # Options might be shuffled in future, but simple for now

class ExamSession(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    questions: List[ExamQuestion]
    start_time: datetime
    end_time: Optional[datetime] = None
    score: Optional[int] = None
    status: str = "in_progress" # in_progress, completed
    answers: List[dict] = [] # {question_id: str, selected_option_id: str, is_correct: bool}

class SubmitAnswerRequest(BaseModel):
    question_id: str
    selected_option_id: str

class ExamResult(BaseModel):
    total_questions: int
    correct_answers: int
    score_percentage: float
    passed: bool # e.g., > 35/40 or similar logic, user said 30 questions. Let's say 25/30 pass.
    details: List[dict] # Detailed breakdown

# Training Mode
class TrainingAnswerRequest(BaseModel):
    question_id: str
    selected_option_id: str

class TrainingResponse(BaseModel):
    is_correct: bool
    explanation: str
    correct_option_id: str
