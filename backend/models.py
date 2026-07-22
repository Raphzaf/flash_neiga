from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, Float, ForeignKey, UniqueConstraint
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
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuestionDB(Base):
    __tablename__ = "questions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    category = Column(String, index=True)
    options = Column(JSON)  # Stored as JSON array
    explanation = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)  # ← COLONNE IMAGE
    created_at = Column(DateTime, default=datetime.utcnow)


class TrafficSignDB(Base):
    __tablename__ = "traffic_signs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    number = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    category = Column(String, index=True, nullable=False)
    explanation = Column(Text, nullable=True)
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
    """Modèle pour enregistrer les transactions de paiement (HYP, Verifone/2Checkout, etc.)"""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=True)
    plan_id = Column(String, index=True, nullable=True)  # code_14d, video_1m, etc.
    
    # Legacy Paddle fields (kept for backward compatibility)
    paddle_transaction_id = Column(String, unique=True, index=True, nullable=True)
    paddle_subscription_id = Column(String, index=True, nullable=True)
    
    # HYP specific fields
    hyp_transaction_id = Column(String, unique=True, index=True, nullable=True)
    hyp_internal_deal_id = Column(String, unique=True, index=True, nullable=True)
    
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    status = Column(String, index=True)  # pending, completed, failed, refunded, cancelled
    event_type = Column(String, nullable=True)  # transaction.completed, subscription.created, etc.
    event_data = Column(JSON, nullable=True)  # Données supplémentaires (Paddle/HYP)
    
    payment_url = Column(String, nullable=True)  # URL de paiement HYP
    callback_data = Column(JSON, nullable=True)  # Données du callback HYP
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
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
    """Abonnements/licences gérés par HYP, Verifone/2Checkout (LCN)."""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    plan_id = Column(String, index=True, nullable=True)  # code_14d, video_1m, etc.
    
    # Legacy fields
    license_id = Column(String, index=True, nullable=True)  # LCN license/subscription id
    product_id = Column(Integer, index=True, nullable=True)
    
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    status = Column(String, index=True)  # active, expired, cancelled
    next_renewal = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserMistakeDB(Base):
    """Mémoire des erreurs d'un élève : chaque question ratée est enregistrée ici
    pour pouvoir être retravaillée depuis la rubrique « Mes questions à retravailler ».
    """
    __tablename__ = "user_mistakes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    question_id = Column(String, index=True, nullable=False)
    times_wrong = Column(Integer, default=0)          # nb total de fois où l'élève s'est trompé
    times_correct_since = Column(Integer, default=0)  # série de bonnes réponses consécutives en révision
    mastered = Column(Boolean, default=False)         # True après 2 bonnes réponses consécutives
    first_wrong_at = Column(DateTime, default=datetime.utcnow)
    last_wrong_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_mistake"),
    )


class AILessonDB(Base):
    """Cache des mini-leçons générées par le coach IA pour une (question, mauvaise réponse).
    Une leçon est réutilisable pour tous les élèves → coût API quasi nul en régime de croisière.
    """
    __tablename__ = "ai_lessons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id = Column(String, index=True, nullable=False)
    selected_option_id = Column(String, nullable=False)
    lesson_json = Column(Text, nullable=False)  # JSON: explication, regle, erreurs_a_eviter, schema_svg
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("question_id", "selected_option_id", name="uq_ai_lesson"),
    )


class SeriesReportDB(Base):
    """Cache du bilan de série généré par le coach IA après un examen/série."""
    __tablename__ = "series_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    session_id = Column(String, unique=True, index=True, nullable=False)
    report_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrapSynthesisDB(Base):
    """Synthèse pédagogique (générée par Claude) des questions pièges les plus fréquentes.
    Régénérable par l'admin ; on ne garde que la dernière version.
    """
    __tablename__ = "trap_synthesis"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    synthesis_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CourseDB(Base):
    """Cours théoriques avec supports vidéo et PDF"""
    __tablename__ = "courses"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    order = Column(Integer, default=0)
    video_url = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
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
    image_url: Optional[str] = None  # ← AJOUTE ICI


class Question(QuestionCreate):
    id: str
    created_at: Optional[datetime] = None  # ← Rends created_at optionnel aussi

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
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None  # compat ascendante (ancien formulaire)


class UserInDB(UserCreate):
    id: str


class User(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


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
    plan_id: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    hyp_transaction_id: Optional[str] = None
    hyp_internal_deal_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: str
    event_type: Optional[str] = None
    event_data: Optional[dict] = None
    payment_url: Optional[str] = None
    callback_data: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    updated_at: datetime


class TransactionCreate(BaseModel):
    """Modèle pour créer une transaction de paiement"""
    user_id: Optional[str] = None
    plan_id: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    hyp_transaction_id: Optional[str] = None
    hyp_internal_deal_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: str
    event_type: Optional[str] = None
    event_data: Optional[dict] = None
    payment_url: Optional[str] = None
    callback_data: Optional[dict] = None


class Subscription(BaseModel):
    """Modèle Pydantic pour les abonnements"""
    id: str
    user_id: Optional[str] = None
    plan_id: Optional[str] = None
    license_id: Optional[str] = None
    product_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str
    next_renewal: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SubscriptionCreate(BaseModel):
    """Modèle pour créer un abonnement"""
    user_id: Optional[str] = None
    plan_id: Optional[str] = None
    license_id: Optional[str] = None
    product_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str
    next_renewal: Optional[datetime] = None
    transaction_id: Optional[str] = None


class CourseCreate(BaseModel):
    """Modèle pour créer un cours"""
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    order: Optional[int] = 0
    video_url: Optional[str] = None
    pdf_url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None


class Course(CourseCreate):
    """Modèle Pydantic pour les cours"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CourseOrderUpdate(BaseModel):
    """Modèle pour mettre à jour l'ordre d'un cours"""
    order: int


class MistakeReviewRequest(BaseModel):
    """Réponse soumise en mode révision depuis « Mes questions à retravailler »."""
    question_id: str
    selected_option_id: str


class MistakeReviewResponse(BaseModel):
    is_correct: bool
    correct_option_id: Optional[str] = None
    explanation: Optional[str] = None
    mastered: bool = False
    times_correct_since: int = 0

