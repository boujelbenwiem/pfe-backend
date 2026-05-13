#initialisation de la base de données
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import get_auth_connection

CREATE_USERS_SEQ_SQL = """
CREATE SEQUENCE IF NOT EXISTS users_id_seq START 1
"""

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY DEFAULT nextval('users_id_seq'),  -- ID unique, auto-incrémenté
    username VARCHAR(100),                     -- Nom d'utilisateur
    email VARCHAR(255) UNIQUE NOT NULL,        -- Email (unique, obligatoire)
    password_hash VARCHAR(255) NOT NULL,       -- Mot de passe haché (obligatoire)
    role VARCHAR(50) NOT NULL,                 -- Rôle: ADMIN, STORE_MANAGER, etc.
    store_id VARCHAR(50),                      -- ID du magasin (pour responsables)
    department VARCHAR(50),                    -- Département (pour CRM,ACHAT...)
    is_active BOOLEAN DEFAULT TRUE,            -- Compte actif ou désactivé
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Date de création
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- Date de modification
)
"""

def init_db():
    """Initialise la base de données en créant les tables nécessaires."""
    conn = get_auth_connection()
    conn.execute(CREATE_USERS_SEQ_SQL)
    conn.execute(CREATE_USERS_TABLE_SQL)
    print("Base de données initialisée avec succès.")


def create_default_admin():
    """Crée un utilisateur admin par défaut si aucun utilisateur n'existe."""
    conn = get_auth_connection()
    result = conn.execute("SELECT id from users where role='ADMIN' LIMIT 1").fetchone()
    if result is None:
        print("Aucun utilisateur admin trouvé. Création d'un utilisateur admin par défaut.")
        hashed_pw = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
        conn.execute("""
            INSERT INTO users (username, email, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, ["Administrator", "admin@bv.fr", hashed_pw, "ADMIN", True])
        print("Utilisateur admin créé avec email 'admin@bv.fr'")


def check_db():
    """Vérifie que la base de données est accessible et que les tables sont créées."""
    try:
        get_auth_connection().execute("SELECT 1")
        print("Connexion à la base de données réussie.")
    except Exception as e:
        print(f"Erreur de connexion à la base de données: {e}")
