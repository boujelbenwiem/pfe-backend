from fastapi import APIRouter, Depends, HTTPException, status, Query
import duckdb
from typing import Optional

from app.schemas.user import (
    UserResponse, 
    UserUpdate, 
    UserDeleteResponse,
    UsersListResponse,
    PasswordChangeRequest
)
from app.services.user_service import UserService
from app.db.session import get_db_connection
from app.core.deps import (
    get_current_user,
    require_admin,
    require_self_or_admin
)
from app.models.user import User, UserRole


router = APIRouter(prefix="/users", tags=["Users"])



# ROUTES POUR L'UTILISATEUR CONNECTÉ

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Mon profil",
    description="Retourne les informations de l'utilisateur connecté."
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Récupère le profil de l'utilisateur connecté."""
    return current_user.to_dict()


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Modifier mon profil",
    description="Permet à un utilisateur de modifier ses propres informations."
)
async def update_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Modifie le profil de l'utilisateur connecté.
    
    Seuls les champs fournis seront modifiés.
    """
    service = UserService(conn)
    
    try:
        updated_user = service.update_user(current_user.id, update_data)
        return updated_user.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/me/change-password",
    summary="Changer mon mot de passe",
    description="Permet à un utilisateur de changer son mot de passe."
)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Change le mot de passe de l'utilisateur connecté.
    
    - **old_password**: Ancien mot de passe
    - **new_password**: Nouveau mot de passe (min 8 caractères)
    """
    from app.core.security import verify_password, hash_password
    from datetime import datetime, timezone
    
    # Vérifier l'ancien mot de passe
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ancien mot de passe incorrect"
        )
    
    # Hacher le nouveau mot de passe
    new_hashed = hash_password(password_data.new_password)
    
    # Mettre à jour
    service = UserService(conn)
    service.db_conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        [new_hashed, datetime.now(timezone.utc), current_user.id]
    )
    
    return {"message": "Mot de passe modifié avec succès"}


@router.delete(
    "/me",
    response_model=UserDeleteResponse,
    summary="Supprimer mon compte",
    description="Permet à un utilisateur de supprimer son propre compte."
)
async def delete_me(
    current_user: User = Depends(get_current_user),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Supprime le compte de l'utilisateur connecté.
    
    Action irréversible !
    """
    service = UserService(conn)
    
    # Sauvegarder l'ID pour la réponse
    user_id = current_user.id
    
    # Supprimer l'utilisateur
    success = service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return UserDeleteResponse(
        message="Compte supprimé avec succès",
        deleted_id=user_id,
        success=True
    )


# ROUTES ADMIN 

@router.get(
    "/",
    response_model=UsersListResponse,
    summary="Liste des utilisateurs (admin)",
    description="Retourne la liste paginée de tous les utilisateurs. Réservé aux administrateurs."
)
async def get_all_users(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Nombre d'éléments par page"),
    role: Optional[str] = Query(None, description="Filtrer par rôle"),
    is_active: Optional[bool] = Query(None, description="Filtrer par statut actif"),
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Liste tous les utilisateurs avec pagination et filtres.
    
    Réservé aux administrateurs.
    """
    service = UserService(conn)
    
    users, total = service.get_all_users(
        page=page,
        per_page=per_page,
        role=role,
        is_active=is_active
    )
    
    return UsersListResponse(
        total=total,
        page=page,
        per_page=per_page,
        users=users
    )


@router.get(
    "/stats/count",
    summary="Statistiques utilisateurs",
    description="Retourne le nombre d'utilisateurs par rôle. Réservé aux administrateurs."
)
async def get_user_stats(
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Retourne des statistiques sur les utilisateurs.
    
    Réservé aux administrateurs.
    """
    service = UserService(conn)
    
    stats = {}
    for role in UserRole:
        stats[role.value] = service.count_users(role=role.value)
    
    stats["total"] = service.count_users()
    
    return stats


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Récupérer un utilisateur",
    description="Récupère les informations d'un utilisateur spécifique."
)
async def get_user(
    user_id: int,
    user: User = Depends(require_self_or_admin()),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Récupère un utilisateur par son ID.
    
    - Un utilisateur normal ne peut voir que son propre profil
    - Un administrateur peut voir n'importe quel profil
    """
    service = UserService(conn)
    target_user = service.get_user_by_id(user_id)
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return target_user.to_dict()


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Modifier un utilisateur",
    description="Modifie les informations d'un utilisateur. Réservé aux administrateurs."
)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Modifie un utilisateur par son ID.
    
    Réservé aux administrateurs.
    """
    service = UserService(conn)
    
    try:
        updated_user = service.update_user(user_id, update_data)
        return updated_user.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{user_id}",
    response_model=UserDeleteResponse,
    summary="Supprimer un utilisateur",
    description="Supprime un utilisateur. Réservé aux administrateurs."
)
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Supprime un utilisateur par son ID.
    
    Réservé aux administrateurs.
    Action irréversible !
    """
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte via cette route. Utilisez DELETE /users/me"
        )
    
    service = UserService(conn)
    
    user_to_delete = service.get_user_by_id(user_id)
    if not user_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    success = service.delete_user(user_id)
    
    return UserDeleteResponse(
        message=f"Utilisateur {user_to_delete.email} supprimé avec succès",
        deleted_id=user_id,
        success=success
    )


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Activer un utilisateur",
    description="Active un compte utilisateur désactivé. Réservé aux administrateurs."
)
async def activate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Active un utilisateur désactivé.
    
    Réservé aux administrateurs.
    """
    service = UserService(conn)
    
    try:
        activated_user = service.activate_user(user_id)
        return activated_user.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Désactiver un utilisateur",
    description="Désactive un compte utilisateur. Réservé aux administrateurs."
)
async def deactivate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    conn: duckdb.DuckDBPyConnection = Depends(get_db_connection)
):
    """
    Désactive un utilisateur.
    
    Réservé aux administrateurs.
    Un utilisateur désactivé ne peut plus se connecter.
    """
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte"
        )
    
    service = UserService(conn)
    
    try:
        deactivated_user = service.deactivate_user(user_id)
        return deactivated_user.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )