from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, Float
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import declarative_base
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid

# Import Base from database module to ensure all models use the same Base
# Support imports both when running from backend/ and from repo root
try:
    from database import Base
except ImportError:
    # When imported as a package from repo root
    from backend.database import Base


# ===== SQLAlchemy DB Models =====
class UserDB(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionDB(Base):
    __tablename__ = "questions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    category = Column(String, index=True, nullable=False)
    options = Column(JSON, nullable=False)  # List[QuestionOption]
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrafficSignDB(Base):
    __tablename__ = "traffic_signs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    number = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    category = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExamSessionDB(Base):
    __tablename__ = "exam_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    status = Column(String, default="in_progress")  # in_progress, completed
    answers = Column(MutableDict.as_mutable(JSON), default=dict)  # {question_id: selected_option_id}
    question_ids = Column(MutableList.as_mutable(JSON), default=list)
    score = Column(Integer, nullable=True)
    passed = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class TransactionDB(Base):
    """Modèle pour enregistrer les transactions de paiement (Verifone/2Checkout, etc.)"""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=True)
    paddle_transaction_id = Column(String, unique=True, index=True, nullable=True)
    paddle_subscription_id = Column(String, index=True, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    status = Column(String, index=True)  # pending, completed, failed, refunded, etc.
    event_type = Column(String, nullable=True)  # transaction.completed, subscription.created, etc.
    event_data = Column(JSON, nullable=True)  # Données supplémentaires de Paddle
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaymentDB(Base):
    """Paiements individuels (Order/Payment via Verifone/2Checkout)."""
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=True)
    order_id = Column(String, index=True, nullable=True)
    product_id = Column(Integer, index=True, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    status = Column(String, index=True)  # received, approved, refunded, etc.
    event_type = Column(String, nullable=True)  # ipn.order, ipn.payment, etc.
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubscriptionDB(Base):
    """Abonnements/licences gérés par Verifone/2Checkout (LCN)."""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=True)
    license_id = Column(String, index=True, nullable=True)  # LCN license/subscription id
    product_id = Column(Integer, index=True, nullable=True)
    status = Column(String, index=True)  # active, canceled, expired, etc.
    next_renewal = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class Transaction(BaseModel):
    """Modèle Pydantic pour les transactions de paiement"""
    id: str
    user_id: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: str
    event_type: Optional[str] = None
    event_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    """Modèle pour créer une transaction de paiement"""
    user_id: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: str
    event_type: Optional[str] = None
    event_data: Optional[dict] = None

