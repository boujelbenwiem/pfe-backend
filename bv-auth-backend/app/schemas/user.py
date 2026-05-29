# Ce fichier contient les schémas Pydantic pour la validation des données utilisateur

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserBase(BaseModel):
    """
    Schéma de base avec les champs communs.
    Tous les autres schémas utilisateur vont hériter de celui-ci.
    """
    username: str = Field(..., min_length=3, max_length=100, description="Nom d'utilisateur")
    email: EmailStr = Field(..., description="Adresse email valide")
    role: str = Field(default="STORE_MANAGER", description="Rôle de l'utilisateur")
    store_id: Optional[str] = Field(None, max_length=50, description="ID du magasin")
    department: Optional[str] = Field(None, max_length=50, description="Département")
    is_active: bool = Field(default=True, description="Compte actif ou désactivé")



class UserRegister(UserBase):
    """
    Schéma pour l'inscription d'un nouvel utilisateur.
    
    Utilisé par: POST /register
    
    Exemple de requête:
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "mon_mot_de_passe_123",
        "role": "STORE_MANAGER",
        "store_id": "BV001"
    }
    """
    password: str = Field(..., min_length=8, description="Mot de passe (min 8 caractères)")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Vérifie que le rôle est valide"""
        from app.models.user import UserRole
        if not UserRole.is_valid(v):
            raise ValueError(f"Rôle invalide. Rôles acceptés: {[r.value for r in UserRole]}")
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Vérifie que le mot de passe est assez fort"""
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class UserLogin(BaseModel):
    """
    Schéma pour la connexion d'un utilisateur.
    """
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """
    Schéma pour la modification d'un utilisateur.
    """
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    store_id: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            from app.models.user import UserRole
            if not UserRole.is_valid(v):
                raise ValueError(f"Rôle invalide. Rôles acceptés: {[r.value for r in UserRole]}")
        return v


class UserResponse(BaseModel):
    """
    Schéma pour la réponse API d'un utilisateur.
    """
    id: int
    username: str
    email: EmailStr
    role: str
    store_id: Optional[str] = None
    department: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        # Permet de créer un UserResponse à partir d'un objet User ou d'un dictionnaire
        from_attributes = True


class UsersListResponse(BaseModel):
    """
    Schéma pour la liste paginée des utilisateurs.
    """
    total: int = Field(..., description="Nombre total d'utilisateurs")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Nombre d'éléments par page")
    users: list[UserResponse] = Field(..., description="Liste des utilisateurs")


class UserDeleteResponse(BaseModel):
    """
    Schéma pour la réponse après suppression d'un utilisateur.
    """
    message: str = Field(..., description="Message de confirmation")
    deleted_id: int = Field(..., description="ID de l'utilisateur supprimé")
    success: bool = Field(default=True)




class PasswordChangeRequest(BaseModel):
    """
    Schéma pour changer le mot de passe.
    """
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Le nouveau mot de passe doit contenir au moins une majuscule")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le nouveau mot de passe doit contenir au moins un chiffre")
        return v


class PasswordResetRequest(BaseModel):
    """
    Schéma pour demander une réinitialisation de mot de passe.
    """
    email: EmailStr = Field(..., description="Adresse email de l'utilisateur")


class PasswordResetConfirm(BaseModel):
    """
    Schéma pour confirmer la réinitialisation de mot de passe avec un token.
    """
    token: str = Field(..., min_length=1, description="Token de réinitialisation")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe")
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class AdminCreateUserRequest(BaseModel):
    """
    Schéma pour la création d'un utilisateur par l'admin.
    """
    username: str = Field(..., min_length=3, max_length=100, description="Nom d'utilisateur")
    email: EmailStr = Field(..., description="Adresse email valide")
    role: str = Field(default="STORE_MANAGER", description="Rôle de l'utilisateur")
    store_id: Optional[str] = Field(None, max_length=50, description="ID du magasin")
    department: Optional[str] = Field(None, max_length=50, description="Département")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        from app.models.user import UserRole
        if not UserRole.is_valid(v):
            raise ValueError(f"Rôle invalide. Rôles acceptés: {[r.value for r in UserRole]}")
        return v


class AdminCreateUserResponse(BaseModel):
    """
    Réponse après création d'un utilisateur par l'admin.
    """
    user: UserResponse = Field(..., description="Données de l'utilisateur créé")
    message: str = Field(..., description="Message de confirmation")
    reset_link_sent: bool = Field(default=True, description="Lien de réinitialisation envoyé par email")