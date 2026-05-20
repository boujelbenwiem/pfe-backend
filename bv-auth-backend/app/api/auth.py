from fastapi import APIRouter, Depends, HTTPException, Response, status
import duckdb

from app.schemas.user import UserRegister, UserLogin, UserResponse
from app.schemas.token import TokenResponse
from app.services.user_service import UserService
from app.db.session import get_db_connection
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.core.config import settings
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


# ROUTES PUBLIQUES 

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
    description="Crée un nouveau compte utilisateur. Le mot de passe est automatiquement haché."
)
async def register(
    user_data: UserRegister,
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Inscription d'un nouvel utilisateur.
    
    - **username**: Nom d'utilisateur 
    - **email**: Adresse email valide
    - **password**: Mot de passe 
    - **role**: Rôle (ADMIN, STORE_MANAGER, MARKETING, CRM, ACHATS)
    - **store_id**: ID du magasin (requis pour STORE_MANAGER)
    - **department**: Département 
    """
    service = UserService(conn)
    
    try:
        user = service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Connexion utilisateur",
    description="Authentifie un utilisateur et retourne un token JWT."
)
async def login(
    response: Response,
    login_data: UserLogin,
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Connexion utilisateur.
    
    - **email**: Adresse email
    - **password**: Mot de passe
    
    Le token JWT est stocké dans un cookie HttpOnly sécurisé.
    """
    service = UserService(conn)
    
    try:
        token_response = service.login(login_data.email, login_data.password)
        response.set_cookie(
            key="access_token",
            value=token_response.access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return token_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    summary="Déconnexion",
    description="Déconnecte l'utilisateur "
)
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    """
    Déconnexion.
    
    Supprime le cookie HttpOnly contenant le token JWT.
    """
    response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")
    return {"message": "Déconnexion réussie"}


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rafraîchir le token",
    description="Génère un nouveau token à partir de l'utilisateur actuel."
)
async def refresh_token(
    response: Response,
    current_user: User = Depends(get_current_user),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Rafraîchit le token JWT.
    
    Génère un nouveau token et met à jour le cookie HttpOnly.
    """
    token_data = {
        "sub": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role
    }
    access_token = create_access_token(token_data)
    
    token_response = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=current_user.to_dict()
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return token_response