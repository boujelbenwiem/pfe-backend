#objectif: hashage et vérification des mots de passe, création et vérification des tokens JWT
import bcrypt
import jwt
import secrets
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

# Token de réinitialisation de mot de passe (stocké en DB)

def _get_token_table_connection():
    """Obtient une connexion et crée la table si nécessaire."""
    import duckdb
    from app.core.config import settings
    
    conn = duckdb.connect(settings.DATABASE_PATH)
    
    # Créer la table si elle n'existe pas
    try:
        conn.execute("CREATE SEQUENCE IF NOT EXISTS password_reset_tokens_seq;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY DEFAULT nextval('password_reset_tokens_seq'),
                user_id INTEGER NOT NULL,
                hashed_token VARCHAR NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
    except Exception as e:
        print(f"⚠️  Erreur création table (peut être déjà existante): {e}")
    
    return conn

def generate_password_reset_token(user_id: int, expires_in_hours: int = 24) -> str:
    """
    Génère un token de réinitialisation de mot de passe sécurisé.
    
    Args:
        user_id: ID de l'utilisateur
        expires_in_hours: Durée de validité du token en heures
    
    Returns:
        Token non-hashé à envoyer à l'utilisateur
    """
    # Générer un token aléatoire sécurisé
    token = secrets.token_urlsafe(32)
    
    # Hasher le token pour le stockage
    hashed_token = hash_password(token)
    
    # Stocker le token dans la base de données
    try:
        conn = _get_token_table_connection()
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        created_at = datetime.now(timezone.utc)
        
        conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, hashed_token, expires_at, created_at, used)
            VALUES (?, ?, ?, ?, FALSE)
            """,
            [user_id, hashed_token, expires_at, created_at]
        )
        # Vérifier que le token a été stocké
        count = conn.execute("SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = ?", [user_id]).fetchone()[0]
        print(f"✅ Token stocké pour user_id={user_id} (total tokens: {count})")
        conn.close()
    except Exception as e:
        print(f"❌ Erreur stockage token: {e}")
        import traceback
        traceback.print_exc()
    
    return token

def verify_password_reset_token(token: str) -> int:
    """
    Vérifie un token de réinitialisation de mot de passe.
    
    Args:
        token: Token non-hashé fourni par l'utilisateur
    
    Returns:
        ID de l'utilisateur si valide
    
    Raises:
        Exception si le token est invalide ou expiré
    """
    try:
        conn = _get_token_table_connection()
        
        # Récupérer tous les tokens non utilisés
        results = conn.execute(
            """
            SELECT id, user_id, hashed_token, expires_at FROM password_reset_tokens
            WHERE used = FALSE
            ORDER BY created_at DESC
            """
        ).fetchall()
        
        print(f"🔍 Vérification token: {len(results)} tokens non utilisés trouvés")
        
        now = datetime.now(timezone.utc)
        
        for token_id, user_id, hashed_token, expires_at in results:
            try:
                # Vérifier l'expiration
                # expires_at peut être naive (sans timezone) dans DuckDB
                expires_at_aware = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at
                if expires_at_aware < now:
                    print(f"⏰ Token {token_id} expiré (expires_at={expires_at})")
                    conn.execute(
                        "UPDATE password_reset_tokens SET used = TRUE WHERE id = ?",
                        [token_id]
                    )
                    continue
                
                # Vérifier le token
                if verify_password(token, hashed_token):
                    print(f"✅ Token vérifié pour user_id={user_id}")
                    conn.close()
                    return user_id
                else:
                    print(f"❌ Token {token_id} ne correspond pas")
            except Exception as e:
                print(f"⚠️ Erreur vérification token {token_id}: {e}")
                continue
        
        conn.close()
    except Exception as e:
        print(f"❌ Erreur vérification token: {e}")
        import traceback
        traceback.print_exc()
    
    raise Exception("Token de réinitialisation invalide ou expiré")

def consume_password_reset_token(token: str) -> None:
    """
    Consomme un token de réinitialisation (le marque comme utilisé).
    
    Args:
        token: Token non-hashé fourni par l'utilisateur
    """
    try:
        conn = _get_token_table_connection()
        
        # Récupérer tous les tokens non utilisés
        results = conn.execute(
            "SELECT id, hashed_token FROM password_reset_tokens WHERE used = FALSE"
        ).fetchall()
        
        for token_id, hashed_token in results:
            try:
                if verify_password(token, hashed_token):
                    conn.execute(
                        "UPDATE password_reset_tokens SET used = TRUE WHERE id = ?",
                        [token_id]
                    )
                    conn.close()
                    return
            except:
                continue
        
        conn.close()
    except Exception as e:
        print(f"Erreur consommation token: {e}")
