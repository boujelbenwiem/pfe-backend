#objectif: hashage et vérification des mots de passe, création et vérification des tokens JWT
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

#fct de hashache et de vérification des mots de passe

def hash_password(password: str) -> str:
    """Hash un mot de passe en utilisant bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si le mot de passe en clair correspond au mot de passe hashé."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

#fct de création et de vérification des tokens JWT

def create_access_token(data: dict) -> str:
    """Crée un token d'accès JWT avec une date d'expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Décode un token d'accès JWT et retourne les données."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token expiré")
    except jwt.InvalidTokenError:
        raise Exception("Token invalide")
