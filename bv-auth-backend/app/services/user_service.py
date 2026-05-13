#logique metier de l'application, gestion des utilisateurs.
import duckdb
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.user import UserUpdate, UserResponse, UserRegister
from app.schemas.token import TokenResponse
from app.models.user import User

class UserService:
    """Service pour la gestion des utilisateurs."""
    def __init__(self, db_conn: duckdb.DuckDBPyConnection):
        """Initialise le service avec une connexion à la base de données."""
        self.db_conn = db_conn

    def register_user(self, user_data: UserRegister) -> dict:
        """Enregistre un nouvel utilisateur dans la base de données."""
        existing=self.get_user_by_email(user_data.email)
        if existing:
            raise ValueError("Email déjà utilisé")
        
        hashed_pw = hash_password(user_data.password)
        now = datetime.now(timezone.utc)

        result=self.db_conn.execute("""
        INSERT INTO users (username, email, password_hash, role, store_id, department, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """, [user_data.username, user_data.email, hashed_pw, user_data.role, user_data.store_id, user_data.department, True, now, now]).fetchone()

        return User.from_row(result).to_dict()
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur en vérifiant son email et mot de passe."""
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    def login(self, email: str, password: str) -> TokenResponse:
        """Gère la logique de connexion d'un utilisateur."""
        user = self.authenticate_user(email, password)
        if not user:
            raise Exception("Email ou mot de passe incorrect")
        self.update_last_login(user.id)
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        }
        access_token = create_access_token(token_data)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=user.to_dict()
        )
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par son ID."""
        result = self.db_conn.execute("SELECT * FROM users WHERE id = ?", [user_id]).fetchone()
        if result:
            return User.from_row(result)
        return None
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son email."""
        result = self.db_conn.execute("SELECT * FROM users WHERE email = ?", [email]).fetchone()
        if result:
            return User.from_row(result)
        return None
    def get_all_users(self, page: int=1,per_page: int=20,role: Optional[str]=None,is_active:Optional[bool]=None) -> Tuple[List[UserResponse], int]:
        """Récupère tous les utilisateurs avec pagination."""
        query = "SELECT * FROM users"
        count_query = "SELECT COUNT(*) FROM users"
        params = []
        
        conditions = []
        if role:
            conditions.append("role = ?")
            params.append(role)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(is_active)
        
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
            query += where_clause
            count_query += where_clause
        
        # Ajouter ORDER BY et LIMIT/OFFSET
        query += " ORDER BY id LIMIT ? OFFSET ?"
        
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        
        # Exécuter la requête
        result = self.db_conn.execute(query, params).fetchall()
        users = [User.from_row(row).to_public_dict() for row in result]
        
        # Compter le total
        total = self.db_conn.execute(count_query, params[:-2] if params else []).fetchone()[0]
        
        return users, total
    
    def update_user(self, user_id: int, update_data: UserUpdate) -> User:
        """
        Modifie les informations d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur à modifier
            update_data: Données à modifier (seulement les champs fournis)
            
        Returns:
            User: L'utilisateur mis à jour
            
        Raises:
            Exception: Si l'utilisateur n'existe pas
        """
        # Vérifier que l'utilisateur existe
        user = self.get_user_by_id(user_id)
        if not user:
            raise Exception("Utilisateur non trouvé")
        
        # Construire la requête de mise à jour dynamiquement
        updates = []
        params = []
        
        if update_data.username is not None:
            updates.append("username = ?")
            params.append(update_data.username)
        
        if update_data.email is not None:
            # Vérifier que le nouvel email n'est pas déjà utilisé
            existing = self.get_user_by_email(update_data.email)
            if existing and existing.id != user_id:
                raise Exception("Cet email est déjà utilisé")
            updates.append("email = ?")
            params.append(update_data.email)
        
        if update_data.role is not None:
            updates.append("role = ?")
            params.append(update_data.role)
        
        if update_data.store_id is not None:
            updates.append("store_id = ?")
            params.append(update_data.store_id)
        
        if update_data.department is not None:
            updates.append("department = ?")
            params.append(update_data.department)
        
        if update_data.is_active is not None:
            updates.append("is_active = ?")
            params.append(update_data.is_active)
        
        if update_data.password is not None:
            hashed = hash_password(update_data.password)
            updates.append("password_hash = ?")
            params.append(hashed)
        
        # Toujours mettre à jour updated_at
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc))
        
        if not updates:
            # Rien à mettre à jour
            return user
        
        # Exécuter la mise à jour
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        self.db_conn.execute(query, params)
        
        # Retourner l'utilisateur mis à jour
        return self.get_user_by_id(user_id)
    
    def update_last_login(self, user_id: int) -> None:
        """
        Met à jour la date de dernière connexion.
        
        Args:
            user_id: ID de l'utilisateur
        """
        self.db_conn.execute("""
            UPDATE users SET updated_at = ? WHERE id = ?
        """, [datetime.now(timezone.utc), user_id])
    
    # ============================================================
    # SUPPRESSION (DELETE)
    # ============================================================
    
    def delete_user(self, user_id: int) -> bool:
        """
        Supprime un utilisateur de la base de données.
        
        Args:
            user_id: ID de l'utilisateur à supprimer
            
        Returns:
            bool: True si supprimé, False si non trouvé
        """
        result = self.db_conn.execute("""
            DELETE FROM users WHERE id = ?
        """, [user_id])
        
        # Vérifier si une ligne a été supprimée
        return result.fetchall() is not None
    
    def deactivate_user(self, user_id: int) -> User:
        """
        Désactive un utilisateur (sans le supprimer).
        
        Args:
            user_id: ID de l'utilisateur à désactiver
            
        Returns:
            User: L'utilisateur désactivé
        """
        return self.update_user(user_id, UserUpdate(is_active=False))
    
    def activate_user(self, user_id: int) -> User:
        """
        Active un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur à activer
            
        Returns:
            User: L'utilisateur activé
        """
        return self.update_user(user_id, UserUpdate(is_active=True))
    
    # ============================================================
    # VÉRIFICATIONS ET UTILITAIRES
    # ============================================================
    
    def check_email_exists(self, email: str) -> bool:
        """
        Vérifie si un email existe déjà.
        
        Args:
            email: Email à vérifier
            
        Returns:
            bool: True si l'email existe
        """
        return self.get_user_by_email(email) is not None
    
    def count_users(self, role: Optional[str] = None) -> int:
        """
        Compte le nombre d'utilisateurs.
        
        Args:
            role: Filtrer par rôle (optionnel)
            
        Returns:
            int: Nombre d'utilisateurs
        """
        if role:
            result = self.db_conn.execute("""
                SELECT COUNT(*) FROM users WHERE role = ?
            """, [role]).fetchone()
        else:
            result = self.db_conn.execute("SELECT COUNT(*) FROM users").fetchone()
        
        return result[0] if result else 0


# ============================================================
# FONCTION D'USINE (FACTORY)
# ============================================================

def get_user_service(conn: duckdb.DuckDBPyConnection) -> UserService:
    """
    Fonction utilitaire pour créer une instance du service.
    
    Utilisation dans les routes API:
    user_service = get_user_service(conn)
    
    Args:
        conn: Connexion DuckDB
        
    Returns:
        UserService: Instance du service utilisateur
    """
    return UserService(conn)