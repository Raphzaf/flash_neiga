from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, func
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
DATA_V3_PATH = ROOT_DIR.parent / "data" / "data_v3.json"

SECRET_KEY = os.environ.get("SECRET_KEY", "demo-secret-key-flash-neiga-sqlite")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flash Neiga API")

# CORS Configuration
# Allow requests from Netlify and local development
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # Use environment variable if set
    origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    # Default origins for development and Netlify deployments
    origins = [
        "http://localhost:3000",           # Local React dev server
        "http://localhost:8000",           # Local backend
        "https://*.netlify.app",           # All Netlify deployments (including previews)
        "https://flash-neiga.netlify.app", # Production Netlify (update with actual URL)
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Important for cookies/auth tokens
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lightweight runtime migration to add missing columns if needed (SQLite)
try:
    with engine.connect() as conn:
        # Add question_ids column to exam_sessions if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS __schema_probe__ (id TEXT);
        """))
        conn.execute(text("ALTER TABLE exam_sessions ADD COLUMN question_ids JSON"))
except Exception:
    # Ignore if column already exists or table missing; created by seed scripts
    pass

# Extra safety: always attach CORS headers for wildcard support
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    # Only add fallback headers if not already set by CORSMiddleware
    # Note: When allow_credentials=True, we can't use wildcard origins
    if "Access-Control-Allow-Origin" not in response.headers:
        origin = request.headers.get("origin", "")
        # Check if origin matches allowed patterns
        if origin:
            for allowed in origins:
                # Exact match
                if origin == allowed:
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    break
                # Wildcard subdomain match (e.g., https://*.netlify.app)
                elif allowed.startswith("https://*."):
                    domain_suffix = allowed[10:]  # Remove "https://*."
                    # Check if origin ends with the domain and has proper structure
                    if origin.startswith("https://") and origin.endswith("." + domain_suffix):
                        response.headers["Access-Control-Allow-Origin"] = origin
                        response.headers["Access-Control-Allow-Credentials"] = "true"
                        break
                # Full wildcard (not recommended with credentials but supported)
                elif allowed == "*":
                    response.headers["Access-Control-Allow-Origin"] = origin
                    break
    response.headers.setdefault("Access-Control-Allow-Methods", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "*")
    return response


# ===== Health Check Endpoint =====
@app.get("/health")
async def health_check():
    """Health check endpoint for Render and monitoring services"""
    return {
        "status": "healthy",
        "service": "flash-neiga-backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


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


def load_questions_from_data_v3(db: Session):
    """Load questions from data_v3.json into database"""
    
    # Find data_v3.json in the data directory
    file_path = DATA_V3_PATH
    
    if not file_path.exists():
        print(f"⚠️  data_v3.json not found at {file_path}")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both list and dict with "questions" key
    questions_list = data if isinstance(data, list) else data.get("questions", [])
    
    imported = 0
    
    for idx, item in enumerate(questions_list, 1):
        try:
            # Check if question already exists (by text)
            existing = db.query(QuestionDB).filter(
                QuestionDB.text == item['text']
            ).first()
            
            if not existing:
                question = QuestionDB(
                    id=str(uuid.uuid4()),
                    text=item['text'],
                    category=item.get('category', 'general'),
                    options=item.get('options', []),
                    explanation=item.get('explanation', '')
                )
                db.add(question)
                imported += 1
                
                if imported % 50 == 0:
                    print(f"   ⏳ Imported {imported} questions...")
        
        except Exception as e:
            print(f"⚠️  Error importing question {idx}: {e}")
            continue
    
    db.commit()
    return imported


@app.on_event("startup")
async def startup():
    """Initialize database, create admin, and load questions on first startup"""
    
    print("🔧 Initializing database...")
    init_db()
    print("✅ Database tables created")
    
    db = SessionLocal()
    try:
        # Create admin user if it doesn't exist
        admin_email = "admin@gmail.com"
        existing_admin = db.query(UserDB).filter(UserDB.email == admin_email).first()
        
        if existing_admin:
            print(f"ℹ️  Admin user already exists: {admin_email}")
        else:
            print(f"📝 Creating admin user: {admin_email}")
            
            admin_user = UserDB(
                id=str(uuid.uuid4()),
                email=admin_email,
                hashed_password=pwd_context.hash("admin")
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print(f"✅ Admin user created successfully!")
            print(f"   Email: {admin_email}")
            print(f"   Password: admin")
            print(f"   User ID: {admin_user.id}")
            print("⚠️  IMPORTANT: Change the admin password after first login!")
        
        # Load questions from data_v3.json if database is empty
        question_count = db.query(QuestionDB).count()
        
        if question_count == 0:
            print("📚 Database is empty, loading questions from data_v3.json...")
            imported = load_questions_from_data_v3(db)
            new_count = db.query(QuestionDB).count()
            print(f"✅ Successfully loaded {new_count} questions from data_v3.json!")
        else:
            print(f"ℹ️  Database already contains {question_count} questions")
            
    except Exception as e:
        logger.error(f"❌ Error during startup: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
    
    print("🚀 Application startup complete!")
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

    @app.get("/api/payments/validate-session")
    async def validate_checkout_session(session_id: str):
        if not STRIPE_SECRET_KEY:
            return {"valid": False, "reason": "stripe_not_configured"}
        if not session_id:
            return {"valid": False, "reason": "missing_session_id"}
        try:
            cs = stripe.checkout.Session.retrieve(session_id)
            valid = (cs.get("payment_status") == "paid") or (cs.get("status") == "complete")
            customer_email = (cs.get("customer_details") or {}).get("email")
            return {
                "valid": bool(valid),
                "status": cs.get("status"),
                "payment_status": cs.get("payment_status"),
                "customer_email": customer_email
            }
        except Exception as e:
            return {"valid": False, "reason": "error", "error": str(e)}

    @app.post("/api/admin/import_file")
    async def import_file(payload: dict, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
        if os.environ.get("ADMIN_TOKEN") and x_admin_token != os.environ.get("ADMIN_TOKEN"):
            raise HTTPException(status_code=401, detail="Unauthorized")
        rel_path = payload.get("path") or "data/data_v3.json"
        file_path = ROOT_DIR.parent / rel_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "questions" in data:
                data = data["questions"]
            imported = 0
            skipped = 0
            for q in data:
                text = q.get("text")
                category = q.get("category") or "Autre"
                explanation = q.get("explanation")
                options = q.get("options") or []
                if not text:
                    skipped += 1
                    continue
                exists = db.query(QuestionDB).filter(and_(QuestionDB.text == text, QuestionDB.category == category)).first()
                if exists:
                    skipped += 1
                    continue
                db.add(QuestionDB(text=text, category=category, options=options, explanation=explanation))
                imported += 1
            db.commit()
            return {"status": "ok", "imported": imported, "skipped": skipped}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

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


# ===== Admin Endpoints =====
@app.get("/api/admin/questions/stats")
async def get_question_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get statistics about questions in the database"""
    try:
        total = db.query(QuestionDB).count()
        
        # Count by category
        categories = db.query(
            QuestionDB.category, 
            func.count(QuestionDB.id)
        ).group_by(QuestionDB.category).all()
        
        by_category = {cat: count for cat, count in categories}
        
        # Get database type from connection string
        db_type = "postgresql" if "postgresql" in str(engine.url) else "sqlite"
        
        return {
            "total_questions": total,
            "by_category": by_category,
            "database_type": db_type,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/import-questions")
async def import_questions(
    source: str = "data_v3",
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually import questions from data_v3.json"""
    try:
        if force:
            # Clear existing questions if force=true
            db.query(QuestionDB).delete()
            db.commit()
            print("🗑️  Cleared existing questions")
        
        imported = load_questions_from_data_v3(db)
        total = db.query(QuestionDB).count()
        
        return {
            "success": True,
            "imported": imported,
            "total": total,
            "message": f"✅ Successfully imported {imported} questions from {source}.json"
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": f"❌ Error importing questions: {str(e)}"
        }


@app.delete("/api/admin/questions/clear")
async def clear_questions(
    confirm: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all questions from database (requires confirmation)"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")
    
    try:
        count = db.query(QuestionDB).count()
        db.query(QuestionDB).delete()
        db.commit()
        
        return {
            "success": True,
            "deleted": count,
            "message": f"✅ Deleted {count} questions"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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
        answers={},
        question_ids=[q.id for q in selected]
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
    # Use stored question_ids count when available, fallback to 30
    total_count = 30
    try:
        if isinstance(exam.question_ids, list) and len(exam.question_ids) > 0:
            total_count = len(exam.question_ids)
    except Exception:
        pass
    
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


@app.get("/api/exam/{exam_id}/details")
async def get_exam_details(
    exam_id: str,
    db: Session = Depends(get_db),
):
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Build detailed question list based on stored question_ids
    detailed_questions = []
    question_ids = exam.question_ids or []
    answers = exam.answers or {}
    correct_count = 0

    for qid in question_ids:
        q = db.query(QuestionDB).filter(QuestionDB.id == qid).first()
        if not q:
            continue
        selected_option_id = answers.get(qid)
        correct_option_id = None
        is_correct = False
        for opt in (q.options or []):
            if opt.get("is_correct"):
                correct_option_id = opt.get("id")
            if selected_option_id and opt.get("id") == selected_option_id and opt.get("is_correct"):
                is_correct = True
        if is_correct:
            correct_count += 1
        detailed_questions.append({
            "question_id": q.id,
            "text": q.text,
            "category": q.category,
            "options": q.options,
            "selected_option_id": selected_option_id,
            "correct_option_id": correct_option_id,
            "is_correct": is_correct
        })

    total_questions = len(question_ids) if question_ids else 30
    return {
        "id": exam.id,
        "user_id": exam.user_id,
        "status": exam.status,
        "score": exam.score,
        "passed": exam.passed,
        "created_at": exam.created_at,
        "completed_at": exam.completed_at,
        "correct_answers": correct_count,
        "total_questions": total_questions,
        "questions": detailed_questions
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
):
    # For now, use guest user
    user_id = "guest"
    exams = db.query(ExamSessionDB).filter(
        and_(
            ExamSessionDB.user_id == user_id,
            ExamSessionDB.status == "completed"
        )
    ).order_by(ExamSessionDB.completed_at.desc()).limit(5).all()
    
    total_errors = 0
    best_category = None
    worst_category = None
    category_errors = {}
    
    for exam in exams:
        for question_id, selected_option_id in exam.answers.items():
            question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
            if question:
                is_correct = False
                for opt in question.options:
                    if opt["id"] == selected_option_id and opt["is_correct"]:
                        is_correct = True

    if category_errors:
        best_category = min(category_errors, key=lambda k: category_errors[k])
        worst_category = max(category_errors, key=lambda k: category_errors[k])

    return {
        "last_exams": [
            {
                "id": e.id,
                "score": e.score,
                "passed": e.passed,
                "completed_at": e.completed_at
            } for e in exams
        ],
        "total_errors": total_errors,
        "best_category": best_category,
        "worst_category": worst_category
    }


@app.get("/api/stats/details")
async def get_stats_details(
    db: Session = Depends(get_db),
):
    # For now, use guest user
    user_id = "guest"
    exams = db.query(ExamSessionDB).filter(
        and_(
            ExamSessionDB.user_id == user_id,
            ExamSessionDB.status == "completed"
        )
    ).order_by(ExamSessionDB.completed_at.desc()).limit(5).all()

    exams_detail = []
    for e in exams:
        total_q = len(e.question_ids or []) or 30
        correct = 0
        q_details = []
        for qid in (e.question_ids or []):
            q = db.query(QuestionDB).filter(QuestionDB.id == qid).first()
            if not q:
                continue
            selected = (e.answers or {}).get(qid)
            correct_opt = None
            is_correct = False
            for opt in (q.options or []):
                if opt.get("is_correct"):
                    correct_opt = opt.get("id")
                if opt.get("id") == selected and opt.get("is_correct"):
                    is_correct = True
            if is_correct:
                correct += 1
            q_details.append({
                "question_id": q.id,
                "text": q.text,
                "category": q.category,
                "selected_option_id": selected,
                "correct_option_id": correct_opt,
                "is_correct": is_correct
            })
        exams_detail.append({
            "id": e.id,
            "score": e.score,
            "passed": e.passed,
            "completed_at": e.completed_at,
            "total_questions": total_q,
            "correct_answers": correct,
            "questions": q_details
        })

    return {
        "exams": exams_detail
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
