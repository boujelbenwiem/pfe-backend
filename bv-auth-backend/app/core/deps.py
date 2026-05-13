# app/core/deps.py
# Ce fichier contient les dépendances FastAPI pour l'authentification

from typing import Optional, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import duckdb

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db_connection
from app.services.user_service import UserService
from app.models.user import User, UserRole
from app.schemas.token import TokenPayload

# ============================================================
# CONFIGURATION DE LA SÉCURITÉ HTTP
# ============================================================

# HTTPBearer est un schéma d'authentification qui attend un header:
# Authorization: Bearer <token>
security = HTTPBearer(auto_error=False)


# ============================================================
# DÉPENDANCE : RÉCUPÉRER LE TOKEN
# ============================================================

async def get_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Extrait le token JWT depuis le cookie HttpOnly 'access_token',
    ou en fallback depuis le header Authorization: Bearer <token>.
    """
    # 1. Lire depuis le cookie HttpOnly (prioritaire)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    # 2. Fallback : header Authorization: Bearer <token>
    if credentials:
        return credentials.credentials
    return None


# ============================================================
# DÉPENDANCE : DÉCODER ET VALIDER LE TOKEN
# ============================================================

async def get_token_payload(
    token: Optional[str] = Depends(get_token)
) -> Optional[TokenPayload]:
    """
    Décode le token JWT et retourne son contenu (payload).
    
    Utilisation:
    @app.get("/me")
    async def get_me(payload: TokenPayload = Depends(get_token_payload)):
        print(payload.email)  # email de l'utilisateur
    
    Returns:
        TokenPayload: Contenu du token décodé
        None: Si pas de token
    
    Raises:
        HTTPException: Si token invalide ou expiré
    """
    if not token:
        return None
    
    try:
        # Décoder le token
        decoded = decode_access_token(token)
        
        # Convertir en TokenPayload Pydantic
        payload = TokenPayload(
            sub=decoded.get("sub"),
            email=decoded.get("email"),
            role=decoded.get("role"),
            exp=decoded.get("exp")
        )
        
        return payload
        
    except Exception:
        # Token invalide ou expiré — ne pas exposer les détails internes
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================
# DÉPENDANCE : RÉCUPÉRER L'UTILISATEUR CONNECTÉ
# ============================================================

async def get_current_user(
    payload: Optional[TokenPayload] = Depends(get_token_payload),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
) -> User:
    """
    Récupère l'utilisateur actuellement connecté à partir du token.
    
    C'est LA dépendance principale à utiliser pour les routes protégées.
    
    Utilisation:
    @app.get("/users/me")
    async def get_my_profile(current_user: User = Depends(get_current_user)):
        return current_user
    
    Returns:
        User: L'utilisateur connecté
    
    Raises:
        HTTPException: Si pas de token, token invalide, ou utilisateur inexistant
    """
    # Vérifier qu'un token a été fourni
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Vérifier que le token contient un user_id
    user_id = payload.get_user_id()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide: pas d'identifiant utilisateur",
        )
    
    # Récupérer l'utilisateur en base
    service = UserService(conn)
    user = service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )
    
    return user


# ============================================================
# DÉPENDANCES POUR LA VÉRIFICATION DES RÔLES
# ============================================================

def require_any_role(allowed_roles: List[str]):
    """
    Factory de dépendance : vérifie que l'utilisateur a l'un des rôles autorisés.
    
    Utilisation:
    @app.get("/dashboard")
    async def dashboard(
        user: User = Depends(require_any_role([UserRole.ADMIN, UserRole.MARKETING]))
    ):
        return {"dashboard": ...}
    
    Args:
        allowed_roles: Liste des rôles autorisés
    
    Returns:
        Dépendance FastAPI
    """
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in [r.value if isinstance(r, UserRole) else r for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé. Permissions insuffisantes."
            )
        return current_user
    return dependency


# Raccourcis pratiques utilisant require_any_role
require_admin = require_any_role([UserRole.ADMIN])
require_store_manager = require_any_role([UserRole.ADMIN, UserRole.STORE_MANAGER])
require_marketing = require_any_role([UserRole.ADMIN, UserRole.MARKETING])
require_crm = require_any_role([UserRole.ADMIN, UserRole.CRM])
require_achats = require_any_role([UserRole.ADMIN, UserRole.ACHATS])


# ============================================================
# DÉPENDANCE : VÉRIFICATION D'ACCÈS À UN MAGASIN SPÉCIFIQUE
# ============================================================

def require_store_access(store_id_param: str = "store_id"):
    """
    Factory de dépendance : vérifie que l'utilisateur a accès à un magasin.
    
    Règles:
    - ADMIN : accès à tous les magasins
    - STORE_MANAGER : accès uniquement à son magasin
    
    Utilisation:
    @app.get("/store/{store_id}/sales")
    async def store_sales(
        store_id: str,
        user: User = Depends(require_store_access())
    ):
        return {"sales": [...]}
    
    Args:
        store_id_param: Nom du paramètre de path contenant l'ID du magasin
    """
    from fastapi import Request

    async def dependency(request: Request, current_user: User = Depends(get_current_user)) -> User:
        store_id = request.path_params.get(store_id_param)
        if not store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID du magasin manquant"
            )
        if not current_user.has_store_access(store_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé à ce magasin"
            )
        return current_user
    return dependency


# ============================================================
# DÉPENDANCE : VÉRIFICATION QUE L'UTILISATEUR EST PROPRIÉTAIRE
# ============================================================

def require_self_or_admin(user_id_param: str = "user_id"):
    """
    Factory de dépendance : vérifie que l'utilisateur accède à son propre profil OU est admin.
    
    Utilisation:
    @app.get("/users/{user_id}")
    async def get_user(
        user_id: int,
        user: User = Depends(require_self_or_admin())
    ):
        return {"user": ...}
    
    Args:
        user_id_param: Nom du paramètre de path contenant l'ID utilisateur cible
    """
    from fastapi import Request

    async def dependency(request: Request, current_user: User = Depends(get_current_user)) -> User:
        target_user_id = request.path_params.get(user_id_param)
        if target_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID utilisateur manquant"
            )
        if current_user.id != int(target_user_id) and current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez accéder qu'à votre propre profil"
            )
        return current_user
    return dependency


# ============================================================
# DÉPENDANCES OPTIONNELLES (SANS ERREUR SI NON AUTHENTIFIÉ)
# ============================================================

async def get_optional_current_user(
    payload: Optional[TokenPayload] = Depends(get_token_payload),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
) -> Optional[User]:
    """
    Version optionnelle : retourne l'utilisateur s'il est authentifié, sinon None.
    
    Utilisation:
    @app.get("/public")
    async def public_route(user: Optional[User] = Depends(get_optional_current_user)):
        if user:
            return {"message": f"Bonjour {user.username}"}
        else:
            return {"message": "Bonjour visiteur"}
    
    Returns:
        User ou None
    """
    if not payload:
        return None
    
    user_id = payload.get_user_id()
    if not user_id:
        return None
    
    service = UserService(conn)
    user = service.get_user_by_id(user_id)
    
    if user and user.is_active:
        return user
    
    return None