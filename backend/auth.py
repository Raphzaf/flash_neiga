"""
Authentication utilities for Flash Neiga API
Extracted to avoid circular imports
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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


def has_active_subscription(db: Session, user_id: str) -> bool:
    """L'élève dispose-t-il d'un abonnement en cours de validité ?"""
    from datetime import datetime
    try:
        from models import SubscriptionDB
    except ImportError:  # pragma: no cover
        from backend.models import SubscriptionDB

    now = datetime.utcnow()
    sub = (
        db.query(SubscriptionDB)
        .filter(
            SubscriptionDB.user_id == user_id,
            SubscriptionDB.status == "active",
        )
        .order_by(SubscriptionDB.created_at.desc())
        .first()
    )
    # Un abonnement résilié reste valable jusqu'à sa date de fin ; c'est le champ
    # end_date qui fait foi, pas seulement le statut.
    return bool(sub and (sub.end_date is None or sub.end_date > now))


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
