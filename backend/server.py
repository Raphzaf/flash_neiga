# backend/server.py

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, func
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import json
# Stripe integration removed
# Support imports both when running from backend/ and from repo root
try:
    from database import engine, SessionLocal, Base, get_db, ensure_schema_updated
except ImportError:
    from backend.database import engine, SessionLocal, Base, get_db, ensure_schema_updated
try:
    from models import (
        UserDB, QuestionDB, TrafficSignDB, ExamSessionDB, TransactionDB,
        UserCreate, User, Question, QuestionCreate, QuestionOption,
        TrafficSign, TrafficSignCreate,
        ExamSession, SubmitAnswerRequest, ExamResult,
        TrainingAnswerRequest, TrainingResponse,
        TokenResponse
    )
except ImportError:
    from backend.models import (
        UserDB, QuestionDB, TrafficSignDB, ExamSessionDB, TransactionDB,
        UserCreate, User, Question, QuestionCreate, QuestionOption,
        TrafficSign, TrafficSignCreate,
        ExamSession, SubmitAnswerRequest, ExamResult,
        TrainingAnswerRequest, TrainingResponse,
        TokenResponse
    )
try:
    from routes.verifone_payments import router as verifone_router
except ImportError:
    from backend.routes.verifone_payments import router as verifone_router
try:
    from routes.twocheckout import router as twocheckout_router
except ImportError:
    from backend.routes.twocheckout import router as twocheckout_router

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

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="Flash Neiga API")

# CORS Configuration
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:8000",
        "https://flash-neiga.netlify.app",
        "https://appflashneiga.netlify.app",
    ]

# Support Netlify wildcard via regex (Starlette doesn't support '*' in allow_origins)
allow_origin_regex = r"https://.*\.netlify\.app$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include external routers
app.include_router(verifone_router)
app.include_router(twocheckout_router)


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
    
    # Check and update schema if needed
    print("🔍 Checking database schema...")
    ensure_schema_updated()
    print("✅ Database schema verified")
    
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
                hashed_password=pwd_context.hash("admin.")
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print(f"✅ Admin user created successfully!")
            print(f"   Email: {admin_email}")
            print(f"   Password: admin.")
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

        # Load traffic signs from bundled JSON if none exist
        def _load_signs_from_json(db: Session) -> int:
            path = ROOT_DIR.parent / "data" / "signs_israel_fr_117.json"
            if not path.exists():
                print(f"⚠️  signs JSON not found at {path}")
                return 0
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    print("⚠️  signs JSON format invalid (expected list)")
                    return 0

                imported_signs = 0
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    raw_id = item.get("id")
                    number = f"IL-{raw_id}" if raw_id is not None else None
                    if not number:
                        continue

                    existing = db.query(TrafficSignDB).filter(TrafficSignDB.number == str(number)).first()
                    if existing:
                        continue

                    sign = TrafficSignDB(
                        number=str(number),
                        name=item.get("nom") or "",
                        description=(item.get("nom") or ""),
                        image_url=item.get("image"),
                        category=item.get("type") or "Autre",
                    )
                    db.add(sign)
                    imported_signs += 1

                db.commit()
                return imported_signs
            except Exception as e:
                logger.error(f"Error importing signs from JSON: {e}", exc_info=True)
                db.rollback()
                return 0

        sign_count = db.query(TrafficSignDB).count()
        if sign_count == 0:
            print("🚸 Loading traffic signs from bundled JSON...")
            imported_signs = _load_signs_from_json(db)
            new_sign_count = db.query(TrafficSignDB).count()
            print(f"✅ Loaded {new_sign_count} traffic signs from JSON")
        else:
            print(f"ℹ️  Database already contains {sign_count} traffic signs")
            
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

    # Stripe integration removed

    # Payments endpoints moved to routes.paddle_payments to avoid duplication

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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/reset-admin-password")
async def reset_admin_password(payload: dict, db: Session = Depends(get_db), x_admin_token: Optional[str] = Header(None)):
    """Reset the admin password to a provided value (default 'admin').
    Secured by ADMIN_TOKEN env var if set.
    Payload: { "email": "admin@gmail.com", "new_password": "admin" }
    """
    if os.environ.get("ADMIN_TOKEN") and x_admin_token != os.environ.get("ADMIN_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    email = payload.get("email") or "admin@gmail.com"
    new_password = payload.get("new_password") or "admin."
    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
    user.hashed_password = hash_password(new_password)
    db.add(user)
    db.commit()
    return {"status": "ok", "email": email}


@app.post("/api/admin/import-questions")
async def import_questions(
    payload: dict = {},
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually import questions from data_v3.json"""
    source = payload.get("source", "data_v3")
    force = payload.get("force", False)
    
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
        raise HTTPException(
            status_code=500,
            detail=f"Error importing questions: {str(e)}"
        )


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
class ExplanationUpdate(BaseModel):
    explanation: Optional[str] = None

@app.get("/api/admin/questions")
async def list_admin_questions(
    missingOnly: bool = False,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List questions for admin management (with optional filter for missing explanation)."""
    try:
        query = db.query(QuestionDB)
        if missingOnly:
            query = query.filter((QuestionDB.explanation == None) | (QuestionDB.explanation == ""))
        items = query.order_by(QuestionDB.created_at.desc()).offset(offset).limit(limit).all()
        return [
            {
                "id": q.id,
                "text": q.text,
                "category": q.category,
                "explanation": q.explanation or "",
                "has_explanation": bool(q.explanation and q.explanation.strip()),
                "created_at": q.created_at.isoformat(),
            }
            for q in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/admin/questions/{question_id}/explanation")
async def update_question_explanation(
    question_id: str,
    payload: ExplanationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update or add explanation for a question."""
    try:
        q = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Question not found")
        q.explanation = (payload.explanation or "").strip()
        db.add(q)
        db.commit()
        db.refresh(q)
        return {
            "success": True,
            "id": q.id,
            "explanation": q.explanation,
            "message": "Explanation updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/questions/{question_id}")
async def delete_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a single question by id."""
    try:
        q = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Question not found")
        db.delete(q)
        db.commit()
        return {"success": True, "deleted": question_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ===== Admin Traffic Signs Endpoints =====
@app.get("/api/admin/signs")
async def list_admin_signs(
    missingOnly: bool = False,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List traffic signs for admin management (with optional filter for missing explanation)."""
    logger.info(f"📋 Admin signs request - missingOnly={missingOnly}, limit={limit}, offset={offset}, user={current_user.email}")
    
    try:
        query = db.query(TrafficSignDB)
        
        if missingOnly:
            logger.info("🔍 Filtering for signs with missing explanations")
            query = query.filter((TrafficSignDB.explanation.is_(None)) | (TrafficSignDB.explanation == ""))
        
        items = query.order_by(TrafficSignDB.created_at.desc()).offset(offset).limit(limit).all()
        logger.info(f"✅ Successfully retrieved {len(items)} traffic signs")
        
        return [
            {
                "id": s.id,
                "number": s.number,
                "name": s.name,
                "description": s.description,
                "image_url": s.image_url,
                "category": s.category,
                "explanation": s.explanation or "",
                "has_explanation": bool(s.explanation and s.explanation.strip()),
                "created_at": s.created_at.isoformat(),
            }
            for s in items
        ]
    except Exception as e:
        logger.error(f"❌ Error in list_admin_signs endpoint: {str(e)}", exc_info=True)
        logger.error(f"   Request params: missingOnly={missingOnly}, limit={limit}, offset={offset}")
        
        # Check if it's a database column error
        error_msg = str(e).lower()
        if 'explanation' in error_msg and ('column' in error_msg or 'attribute' in error_msg or 'no such column' in error_msg):
            raise HTTPException(
                status_code=500, 
                detail="Database schema error: 'explanation' column is missing from traffic_signs table. Please run the migration script or restart the application."
            )
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.patch("/api/admin/signs/{sign_id}/explanation")
async def update_sign_explanation(
    sign_id: str,
    payload: ExplanationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update or add explanation for a traffic sign."""
    try:
        s = db.query(TrafficSignDB).filter(TrafficSignDB.id == sign_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Traffic sign not found")
        s.explanation = (payload.explanation or "").strip()
        db.add(s)
        db.commit()
        db.refresh(s)
        return {
            "success": True,
            "id": s.id,
            "explanation": s.explanation,
            "message": "Explanation updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/signs/{sign_id}")
async def delete_sign(
    sign_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a single traffic sign by id."""
    try:
        s = db.query(TrafficSignDB).filter(TrafficSignDB.id == sign_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Traffic sign not found")
        db.delete(s)
        db.commit()
        return {"success": True, "deleted": sign_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/questions", response_model=List[Question])
async def get_questions(
    category: Optional[List[str]] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(QuestionDB)
    if category and len(category) > 0:
        query = query.filter(QuestionDB.category.in_(category))
    if q:
        like_expr = f"%{q}%"
        query = query.filter(
            (QuestionDB.text.ilike(like_expr)) |
            (QuestionDB.explanation.ilike(like_expr))
        )
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
    """Return traffic signs from DB; fallback to bundled JSON if DB unavailable.

    Prevents 500 errors in case of DB/table issues by serving static data.
    """
    try:
        signs = db.query(TrafficSignDB).all()
        if signs:
            return [
                TrafficSign(
                    id=s.id,
                    number=s.number,
                    name=s.name,
                    description=s.description,
                    image_url=s.image_url,
                    category=s.category,
                )
                for s in signs
            ]
    except Exception as e:
        logger.error(f"Error fetching signs from DB: {e}", exc_info=True)

    # Fallback: load from packaged JSON
    fallback_path = ROOT_DIR.parent / "data" / "signs_israel_fr_117.json"
    if fallback_path.exists():
        try:
            with fallback_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                return [
                    TrafficSign(
                        id=str(f"IL-{item.get('id')}") if item.get("id") is not None else str(uuid.uuid4()),
                        number=str(f"IL-{item.get('id')}") if item.get("id") is not None else "",
                        name=item.get("nom") or "",
                        description=item.get("nom") or "",
                        image_url=item.get("image"),
                        category=item.get("type") or "Autre",
                    )
                    for item in raw
                    if isinstance(item, dict)
                ]
        except Exception as e:
            logger.error(f"Error loading fallback signs JSON: {e}", exc_info=True)

    # If nothing available, return empty list instead of 500
    return []


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
            "is_correct": is_correct,
            "explanation": q.explanation
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
