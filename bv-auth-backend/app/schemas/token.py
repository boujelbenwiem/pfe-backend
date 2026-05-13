# Ce fichier contient les schémas Pydantic pour les tokens JWT

from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.user import UserResponse


class Token(BaseModel):
    """
    Schéma de base pour un token JWT.
    """
    access_token: str = Field(..., description="Le token JWT à utiliser pour l'authentification")
    token_type: str = Field(default="bearer", description="Type de token (toujours 'bearer')")


class TokenResponse(Token):
    """
    Schéma pour la réponse après connexion réussie.

    """
    expires_in: int = Field(..., description="Durée de validité en minutes")
    user: UserResponse = Field(..., description="Informations publiques de l'utilisateur")


class TokenPayload(BaseModel):
    """
    Schéma pour le contenu d'un token JWT (après décodage).
    
    """
    sub: Optional[str] = Field(None, description="ID de l'utilisateur (subject)")
    email: Optional[str] = Field(None, description="Email de l'utilisateur")
    role: Optional[str] = Field(None, description="Rôle de l'utilisateur")
    exp: Optional[int] = Field(None, description="Timestamp d'expiration")
    
    def get_user_id(self) -> Optional[int]:
        """Retourne l'ID utilisateur comme entier"""
        if self.sub:
            try:
                return int(self.sub)
            except ValueError:
                return None
        return None


class TokenRefreshRequest(BaseModel):
    """
    Schéma pour rafraîchir un token (optionnel).

    """
    refresh_token: str = Field(..., description="Token de rafraîchissement")


class ErrorResponse(BaseModel):
    """
    Schéma standard pour les réponses d'erreur.
    """
    detail: str = Field(..., description="Message d'erreur détaillé")
    code: Optional[str] = Field(None, description="Code d'erreur (pour le frontend)")
    status_code: int = Field(..., description="Code HTTP")