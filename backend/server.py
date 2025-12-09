from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta, timezone
import os
import logging
from pathlib import Path
from typing import List, Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import json
import stripe

from database import engine, SessionLocal, Base, get_db
from models import (
    UserDB, QuestionDB, TrafficSignDB, ExamSessionDB,
    UserCreate, User, Question, QuestionCreate, QuestionOption,
    TrafficSign, TrafficSignCreate,
    ExamSession, SubmitAnswerRequest, ExamResult,
    TrainingAnswerRequest, TrainingResponse,
    TokenResponse
)

# ===== Config =====
ROOT_DIR = Path(__file__).parent
SAMPLE_QUESTIONS_PATH = ROOT_DIR.parent / "data" / "sample_questions.json"

SECRET_KEY = os.environ.get("SECRET_KEY", "demo-secret-key-flash-neiga-sqlite")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flash Neiga API")

# CORS - must be first middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Extra safety: always attach CORS headers
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    # If not already set by CORSMiddleware, attach permissive headers
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "*")
    return response


# ===== Init Tables =====
def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")


# ===== Auth Helpers =====
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return User(id=user.id, email=user.email)


# ===== Init Data =====
def init_sample_data(db: Session):
    """Load sample questions on startup if DB is empty"""
    try:
        # Check if questions table has data
        count = db.query(QuestionDB).count()
        if count > 0:
            return  # Already has data
        
        if SAMPLE_QUESTIONS_PATH.exists():
            with open(SAMPLE_QUESTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Check if data is a list or a dict with "questions" key
                questions_list = data if isinstance(data, list) else data.get("questions", [])
                
                for q in questions_list:
                    question = QuestionDB(
                        id=str(uuid.uuid4()),
                        text=q["text"],
                        category=q["category"],
                        options=q["options"],
                        explanation=q.get("explanation")
                    )
                    db.add(question)
                db.commit()
                logger.info(f"Loaded {len(questions_list)} sample questions")
    except Exception as e:
        logger.warning(f"Could not load sample questions: {e}")
        db.rollback()


@app.on_event("startup")
async def startup():
    init_db()
    db = SessionLocal()
    init_sample_data(db)
    db.close()
    logger.info("Application startup complete")

    # ===== Admin Import Official =====
    def _map_official_question(raw: dict):
        text = raw.get("Question") or raw.get("question") or ""
        category = raw.get("Sujet") or raw.get("Category") or "Autre"
        explanation = raw.get("Explication") or raw.get("explanation") or None
        # L’API officielle ne fournit pas d'options QCM
        options = []
        return text, category, explanation, options


    @app.post("/api/admin/import_official")
    async def import_official(db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
        # Simple protection: require a token header if configured (optional for now)
        # In production, integrate proper auth/roles.
        if os.environ.get("ADMIN_TOKEN") and x_admin_token != os.environ.get("ADMIN_TOKEN"):
            raise HTTPException(status_code=401, detail="Unauthorized")

        API_URL = "https://www.gov.il/fr/departments/dynamiccollectors/theoryexamhe_data"
        page_size = 1000
        skip = 0
        imported = 0
        skipped = 0

        try:
            while True:
                url = f"{API_URL}?skip={skip}"
                import requests
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                body = r.json()
                chunk = body.get("data", [])
                if not chunk:
                    break

                for raw in chunk:
                    text, category, explanation, options = _map_official_question(raw)
                    if not text:
                        skipped += 1
                        continue
                    # Deduplicate on text+category
                    existing = db.query(QuestionDB).filter(
                        and_(QuestionDB.text == text, QuestionDB.category == category)
                    ).first()
                    if existing:
                        skipped += 1
                        continue
                    q = QuestionDB(
                        text=text,
                        category=category,
                        options=options,
                        explanation=explanation,
                    )
                    db.add(q)
                    imported += 1
                db.commit()

                if len(chunk) < page_size:
                    break
                skip += page_size

            return {"status": "ok", "imported": imported, "skipped": skipped}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    # ===== Payments (Stripe) =====
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_PRICE_LOOKUP = {
        # Map plan keys to Stripe Price lookup_keys configured in your Stripe Dashboard
        # e.g., "code_14d": "code_14d",
        # Update these to match your actual Stripe Price lookup keys
        "code_14d": "code_14d",
        "code_30d": "code_30d",
        "code_week": "code_week",
        "video_1m": "video_1m",
        "video_2m": "video_2m",
        "video_3m": "video_3m",
    }

    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY

    @app.post("/api/payments/create-checkout-session")
    async def create_checkout_session(payload: dict):
        if not STRIPE_SECRET_KEY:
            raise HTTPException(status_code=500, detail="Stripe not configured: set STRIPE_SECRET_KEY env var")
        plan_key = payload.get("plan_key")
        explicit_price_id = payload.get("price_id")
        if not explicit_price_id and (not plan_key or plan_key not in STRIPE_PRICE_LOOKUP):
            raise HTTPException(status_code=400, detail=f"Provide 'price_id' or a valid 'plan_key'. Received plan_key='{plan_key}'.")
        try:
            price_id = explicit_price_id
            if not price_id:
                price_list = stripe.Price.list(
                    lookup_keys=[STRIPE_PRICE_LOOKUP[plan_key]], expand=["data.product"]
                )
                if not price_list.data:
                    raise HTTPException(status_code=400, detail="Stripe price not found for lookup_key")
                price_id = price_list.data[0].id
            session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"quantity": 1, "price": price_id}],
                success_url="http://localhost:3000/pricing/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:3000/pricing/cancel",
            )
            return {"url": session.url}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/payments/create-portal-session")
    async def create_portal_session(payload: dict):
        if not STRIPE_SECRET_KEY:
            raise HTTPException(status_code=500, detail="Stripe not configured")
        checkout_session_id = payload.get("session_id")
        if not checkout_session_id:
            raise HTTPException(status_code=400, detail="Missing session_id")
        try:
            checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)
            session = stripe.billing_portal.Session.create(
                customer=checkout_session.customer,
                return_url="http://localhost:3000/pricing",
            )
            return {"url": session.url}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/payments/health")
    async def payments_health():
        return {
            "stripe_configured": bool(STRIPE_SECRET_KEY),
            "configured_lookup_keys": list(STRIPE_PRICE_LOOKUP.values()),
        }

# ===== Dev seed endpoint (optional) =====
@app.post("/api/dev/seed")
async def dev_seed(db: Session = Depends(get_db)):
    try:
        count = db.query(QuestionDB).count()
        if count >= 30:
            return {"status": "ok", "message": "DB already seeded", "count": count}
        import random
        # Simple seed: create 40 demo questions
        for i in range(40):
            opts = []
            correct_idx = random.randint(0, 3)
            for j in range(4):
                opts.append({
                    "id": str(uuid.uuid4()),
                    "text": f"Option {j+1}",
                    "is_correct": j == correct_idx
                })
            q = QuestionDB(
                id=str(uuid.uuid4()),
                text=f"Question de démonstration {i+1}",
                category=random.choice(["Priorité", "Signalisation", "Vitesse", "Conduite"]),
                options=opts,
                explanation="Explication de démonstration."
            )
            db.add(q)
        db.commit()
        return {"status": "ok", "message": "Seeded demo questions", "count": db.query(QuestionDB).count()}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===== Auth Endpoints =====
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(UserDB).filter(UserDB.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user_id = str(uuid.uuid4())
    user = UserDB(
        id=user_id,
        email=user_in.email,
        hashed_password=hash_password(user_in.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=access_token)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=access_token)


@app.get("/api/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ===== Question Endpoints =====
@app.get("/api/questions", response_model=List[Question])
async def get_questions(
    category: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    query = db.query(QuestionDB)
    if category and len(category) > 0:
        query = query.filter(QuestionDB.category.in_(category))
    questions = query.all()
    return [
        Question(
            id=q.id,
            text=q.text,
            category=q.category,
            options=[QuestionOption(**opt) for opt in q.options],
            explanation=q.explanation,
            created_at=q.created_at
        )
        for q in questions
    ]


@app.post("/api/questions", response_model=Question)
async def create_question(
    question_in: QuestionCreate,
    db: Session = Depends(get_db)
):
    question = QuestionDB(
        id=str(uuid.uuid4()),
        text=question_in.text,
        category=question_in.category,
        options=[opt.dict() for opt in question_in.options],
        explanation=question_in.explanation
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    
    return Question(
        id=question.id,
        text=question.text,
        category=question.category,
        options=[QuestionOption(**opt) for opt in question.options],
        explanation=question.explanation,
        created_at=question.created_at
    )


# ===== Traffic Signs Endpoints =====
@app.get("/api/signs", response_model=List[TrafficSign])
async def get_signs(db: Session = Depends(get_db)):
    signs = db.query(TrafficSignDB).all()
    return [
        TrafficSign(
            id=s.id,
            number=s.number,
            name=s.name,
            description=s.description,
            image_url=s.image_url,
            category=s.category
        )
        for s in signs
    ]


# ===== Exam Endpoints =====
@app.post("/api/exam/start")
async def start_exam(
    db: Session = Depends(get_db),
):
    import random
    # Fetch all questions and filter for playable ones (>=2 options, at least one correct)
    all_questions = db.query(QuestionDB).all()

    def is_playable(q: QuestionDB) -> bool:
        try:
            opts = q.options or []
            if not isinstance(opts, list):
                return False
            if len(opts) < 2:
                return False
            return any(bool(o.get("is_correct")) for o in opts if isinstance(o, dict))
        except Exception:
            return False

    playable = [q for q in all_questions if is_playable(q)]

    # Fallback: seed demo questions if not enough playable
    if len(playable) < 30:
        try:
            await dev_seed(db)  # seed demo questions
            all_questions = db.query(QuestionDB).all()
            playable = [q for q in all_questions if is_playable(q)]
        except Exception:
            pass

    selected_pool = playable if len(playable) > 0 else all_questions
    selected_count = min(30, len(selected_pool))
    selected = random.sample(selected_pool, selected_count) if selected_count > 0 else []
    
    # Create exam session
    exam_id = str(uuid.uuid4())
    exam = ExamSessionDB(
        id=exam_id,
        user_id="guest",
        status="in_progress",
        answers={}
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    # Return session with questions embedded for the client runner
    return {
        "id": exam.id,
        "user_id": exam.user_id,
        "status": exam.status,
        "answers": [],
        "created_at": exam.created_at,
        "questions": [
            {
                "question_id": q.id,
                "text": q.text,
                "category": q.category,
                "options": q.options,
                "image_url": None,
            } for q in selected
        ]
    }


@app.get("/api/exam/{exam_id}", response_model=ExamSession)
async def get_exam(
    exam_id: str,
    db: Session = Depends(get_db),
):
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    return ExamSession(
        id=exam.id,
        user_id=exam.user_id,
        status=exam.status,
        answers=exam.answers,
        score=exam.score,
        passed=exam.passed,
        created_at=exam.created_at
    )


@app.post("/api/exam/{exam_id}/answer")
async def submit_answer(
    exam_id: str,
    answer: SubmitAnswerRequest,
    db: Session = Depends(get_db),
):
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Update answer
    if exam.answers is None:
        exam.answers = {}
    exam.answers[answer.question_id] = answer.selected_option_id
    db.commit()
    
    return {"status": "ok"}


@app.post("/api/exam/{exam_id}/finish")
async def finish_exam(
    exam_id: str,
    db: Session = Depends(get_db),
):
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Calculate score
    correct_count = 0
    total_count = 30
    
    for question_id, selected_option_id in exam.answers.items():
        question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
        if question:
            for opt in question.options:
                if opt["id"] == selected_option_id and opt["is_correct"]:
                    correct_count += 1
                    break
    
    score = int((correct_count / total_count) * 100)
    passed = correct_count >= 25  # 25/30 minimum
    
    exam.status = "completed"
    exam.score = score
    exam.passed = passed
    exam.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(exam)
    
    return {
        "id": exam.id,
        "score": score,
        "passed": passed,
        "correct_answers": correct_count,
        "total_questions": total_count
    }


# ===== Training Endpoint =====
@app.post("/api/training/check", response_model=TrainingResponse)
async def check_training_answer(
    answer: TrainingAnswerRequest,
    db: Session = Depends(get_db)
):
    question = db.query(QuestionDB).filter(QuestionDB.id == answer.question_id).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    is_correct = False
    correct_option_id = None
    
    for opt in question.options:
        if opt["is_correct"]:
            correct_option_id = opt["id"]
            if opt["id"] == answer.selected_option_id:
                is_correct = True
            break
    
    return TrainingResponse(
        is_correct=is_correct,
        explanation=question.explanation,
        correct_option_id=correct_option_id
    )


# ===== Stats Endpoints =====
@app.get("/api/stats/summary")
async def get_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get last 5 completed exams
    exams = db.query(ExamSessionDB).filter(
        and_(
            ExamSessionDB.user_id == current_user.id,
            ExamSessionDB.status == "completed"
        )
    ).order_by(ExamSessionDB.completed_at.desc()).limit(5).all()
    
    total_errors = 0
    best_category = None
    worst_category = None
    category_stats = {}
    
    for exam in exams:
        for question_id, selected_option_id in exam.answers.items():
            question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
            if question:
                is_correct = False
                for opt in question.options:
                    if opt["id"] == selected_option_id and opt["is_correct"]:
                        is_correct = True
                        break
                
                if not is_correct:
                    total_errors += 1
                
                cat = question.category
                if cat not in category_stats:
                    category_stats[cat] = {"correct": 0, "total": 0}
                category_stats[cat]["total"] += 1
                if is_correct:
                    category_stats[cat]["correct"] += 1
    
    if category_stats:
        best_category = max(category_stats.items(), key=lambda x: x[1]["correct"] / max(x[1]["total"], 1))[0]
        worst_category = min(category_stats.items(), key=lambda x: x[1]["correct"] / max(x[1]["total"], 1))[0]
    
    return {
        "total_errors": total_errors,
        "best_category": best_category,
        "worst_category": worst_category,
        "recent_exams_count": len(exams),
        "average_score": int(sum(e.score for e in exams if e.score) / len(exams)) if exams else 0
    }


@app.get("/api/stats/activity")
async def get_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exams = db.query(ExamSessionDB).filter(
        and_(
            ExamSessionDB.user_id == current_user.id,
            ExamSessionDB.status == "completed"
        )
    ).order_by(ExamSessionDB.completed_at.desc()).limit(20).all()
    
    return [
        {
            "id": e.id,
            "score": e.score,
            "passed": e.passed,
            "created_at": e.created_at,
            "completed_at": e.completed_at
        }
        for e in exams
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
