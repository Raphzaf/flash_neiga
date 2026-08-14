"""
Authentication utilities for Flash Neiga API
Extracted to avoid circular imports
"""
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional
import os

# Support imports both when running from backend/ and from repo root
try:
    from database import get_db
    from models import UserDB, User
except ImportError:
    from backend.database import get_db
    from backend.models import UserDB, User

SECRET_KEY = os.environ.get("SECRET_KEY", "demo-secret-key-flash-neiga-sqlite")
ALGORITHM = "HS256"

security = HTTPBearer()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Longueur minimale imposée partout (inscription, rattachement d'un paiement,
# réinitialisation depuis le CRM) pour éviter les règles divergentes.
MIN_PASSWORD_LENGTH = 6


# ===== Identifiants =====
def normalize_email(email: Optional[str]) -> str:
    """Forme canonique d'un email : sans espaces et en minuscules.

    Les élèves saisissent souvent leur email avec une majuscule initiale (ou un
    espace ajouté par le clavier du téléphone). Sans normalisation, le compte
    créé et le compte recherché à la connexion peuvent différer.
    """
    return (email or "").strip().lower()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe sans jamais lever d'exception.

    Un hash absent ou illisible (compte importé, donnée corrompue) doit se
    traduire par « identifiants invalides », pas par une erreur 500.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def validate_password(password: Optional[str]) -> str:
    """Contrôle la longueur du mot de passe et renvoie la valeur nettoyée."""
    password = password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.",
        )
    return password


def find_user_by_email(db: Session, email: Optional[str]) -> Optional[UserDB]:
    """Recherche un compte par email, sans tenir compte de la casse."""
    normalized = normalize_email(email)
    if not normalized:
        return None
    return db.query(UserDB).filter(func.lower(UserDB.email) == normalized).first()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the JWT token
    """
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
    return User(
        id=user.id,
        email=user.email,
        first_name=getattr(user, "first_name", None),
        last_name=getattr(user, "last_name", None),
    )


# Version « soft » de l'authentification : ne lève jamais d'erreur.
# Utilisée sur des endpoints publics (entraînement) où l'on veut savoir
# qui est l'élève s'il est connecté, sans bloquer l'accès anonyme.
optional_security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Retourne l'utilisateur courant si un token JWT valide est présent, sinon None.

    Ne lève jamais d'exception : un token absent ou invalide donne simplement None,
    ce qui permet de conserver l'accès anonyme aux endpoints d'entraînement.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user is None:
        return None
    return User(id=user.id, email=user.email)


# ===== Administration =====
# Les comptes administrateurs sont désignés par leur email via ADMIN_EMAILS
# (liste séparée par des virgules). Valeur par défaut : le compte admin créé
# au démarrage. Aucun secret n'est codé en dur.
DEFAULT_ADMIN_EMAILS = "admin@gmail.com"


def admin_emails() -> set:
    raw = os.environ.get("ADMIN_EMAILS") or DEFAULT_ADMIN_EMAILS
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin_email(email: Optional[str]) -> bool:
    return bool(email) and email.strip().lower() in admin_emails()


# Statuts qui donnent encore accès au contenu tant que la date de fin n'est pas
# passée. « cancelled » en fait partie : résilier signifie « ne pas renouveler »,
# pas « perdre immédiatement ce qui est déjà payé ».
VALID_SUBSCRIPTION_STATUSES = ("active", "cancelled")


def current_subscription(db: Session, user_id: str):
    """Abonnement encore valable de l'élève, s'il en a un."""
    from datetime import datetime
    try:
        from models import SubscriptionDB
    except ImportError:  # pragma: no cover
        from backend.models import SubscriptionDB

    now = datetime.utcnow()
    candidates = (
        db.query(SubscriptionDB)
        .filter(
            SubscriptionDB.user_id == user_id,
            SubscriptionDB.status.in_(VALID_SUBSCRIPTION_STATUSES),
        )
        .order_by(SubscriptionDB.created_at.desc())
        .all()
    )
    # C'est la date de fin qui fait foi, pas seulement le statut.
    return next((s for s in candidates if s.end_date is None or s.end_date > now), None)


def has_active_subscription(db: Session, user_id: str) -> bool:
    """L'élève dispose-t-il d'un abonnement en cours de validité ?"""
    return current_subscription(db, user_id) is not None


async def require_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Réserve l'accès au contenu aux élèves ayant un abonnement actif.

    Répond 402 (Payment Required) pour que le front puisse rediriger vers la
    page Formules sans confondre ce cas avec une session expirée (401) ou un
    accès administrateur refusé (403).
    Les administrateurs ne sont pas soumis au paywall.
    """
    if is_admin_email(current_user.email):
        return current_user

    if not has_active_subscription(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Un abonnement actif est nécessaire pour accéder à ce contenu.",
        )
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Autorise uniquement les comptes administrateurs.

    À utiliser sur toute route exposant des données personnelles (CRM) :
    l'utilisateur doit être authentifié ET figurer dans ADMIN_EMAILS.
    """
    if not is_admin_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user
