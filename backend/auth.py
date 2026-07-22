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
