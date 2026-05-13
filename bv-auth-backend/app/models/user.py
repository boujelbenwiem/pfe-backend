#structure utilidateur
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class UserRole(str, Enum):
    """Rôles possibles pour les utilisateurs."""
    ADMIN = "ADMIN"
    STORE_MANAGER = "STORE_MANAGER"
    MARKETING = "MARKETING"
    CRM = "CRM"
    ACHATS = "ACHATS"

    @classmethod
    def is_valid(cls, role: str) -> bool:
        """Vérifie si un rôle donné est valide."""
        return role in cls._value2member_map_
    
class User:
    """Modèle de données pour un utilisateur."""
    def __init__(
        self,
        id: int,
        username: str,
        email: str,
        password_hash: str,
        role: str,
        store_id: Optional[str] = None,
        department: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        if not UserRole.is_valid(role):
            raise ValueError(f"Rôle invalide: {role}. Rôles valides: {[r.value for r in UserRole]}")
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.store_id = store_id
        self.department = department
        self.is_active = is_active
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    @classmethod
    def from_row(cls, row: tuple) -> "User":
        """Crée un objet User à partir d'un tuple retourné par DuckDB.
        Ordre attendu: id, username, email, password_hash, role, store_id, department, is_active, created_at, updated_at
        """
        return cls(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            role=row[4],
            store_id=row[5],
            department=row[6],
            is_active=row[7],
            created_at=row[8],
            updated_at=row[9],
        )

    def to_dict(self):
        """Convertit l'objet User en dictionnaire (sans le mot de passe)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "store_id": self.store_id,
            "department": self.department,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    def to_public_dict(self):
        """Retourne un dictionnaire avec les informations publiques de l'utilisateur (sans le mot de passe)."""
        return self.to_dict()
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur a le rôle d'administrateur."""
        return self.role == UserRole.ADMIN
    def is_store_manager(self) -> bool:
        """Vérifie si l'utilisateur a le rôle de responsable de magasin."""
        return self.role == UserRole.STORE_MANAGER
    def is_marketing(self) -> bool:
        """Vérifie si l'utilisateur a le rôle de marketing."""
        return self.role == UserRole.MARKETING
    def is_crm(self) -> bool:
        """Vérifie si l'utilisateur a le rôle de CRM."""
        return self.role == UserRole.CRM
    def is_achats(self) -> bool:
        """Vérifie si l'utilisateur a le rôle d'achats."""
        return self.role == UserRole.ACHATS
    def has_store_access(self, store_id: str) -> bool:
        """Vérifie si l'utilisateur a accès à un magasin spécifique (pour les responsables de magasin)."""
        if self.is_admin():
            return True  # Les admins ont accès à tous les magasins
        if self.is_store_manager() and self.store_id == store_id:
            return True
        return False
    
    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"
    

