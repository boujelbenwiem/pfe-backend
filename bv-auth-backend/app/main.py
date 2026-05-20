# app/main.py
# Point d'entrée de l'application FastAPI

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.core.config import settings
from app.db.init_db import init_db, create_default_admin, check_db
from app.api import auth, users
from app.api.chat import router as chat_router
from app.api.chat_history import router as chat_history_router

# CONFIGURATION DES LOGS

# Configuration du système de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# GESTION DU CYCLE DE VIE (LIFESPAN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gère les événements au démarrage et à l'arrêt de l'application.
    
    - startup: Initialise la base de données et crée l'admin par défaut
    - shutdown: Nettoie les ressources (si nécessaire)
    
    Ce contexte est automatiquement utilisé par FastAPI.
    """
    # ---- DÉMARRAGE (startup) ----
    logger.info("=" * 50)
    logger.info("🚀 Démarrage de l'application BV Auth Backend")
    logger.info("=" * 50)
    
    try:
        # Initialiser la base de données
        logger.info("📁 Initialisation de la base de données...")
        init_db()
        logger.info("   ✅ Base de données prête")
        
        # Créer un compte admin par défaut si nécessaire
        logger.info("👑 Vérification du compte administrateur...")
        create_default_admin()
        logger.info("   ✅ Compte admin vérifié")
        
        # Afficher l'état de la base (optionnel, pour le debug)
        check_db()
        
        logger.info("=" * 50)
        logger.info("✅ Application démarrée avec succès !")
        logger.info(f"📡 API disponible sur http://localhost:8000")
        logger.info(f"📚 Documentation Swagger: http://localhost:8000/docs")
        logger.info(f"📖 Documentation ReDoc: http://localhost:8000/redoc")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage: {str(e)}")
        raise
    
    yield  # L'application tourne ici
    
    # ---- ARRÊT (shutdown) ----
    logger.info("=" * 50)
    logger.info("🛑 Arrêt de l'application BV Auth Backend")
    logger.info("=" * 50)

# CRÉATION DE L'APPLICATION FASTAPI


# Créer l'instance FastAPI avec la gestion du cycle de vie
app = FastAPI(
    title="BV Auth Backend",
    description="""
    ## API d'authentification modulaire pour l'écosystème BV
    
    Cette API fournit :
    - 🔐 Authentification JWT
    - 👥 Gestion des utilisateurs (CRUD)
    - 🎭 Gestion des rôles (ADMIN, STORE_MANAGER, MARKETING, CRM, ACHATS)
    - 🏪 Contrôle d'accès par magasin
    
    ### Documentation interactive
    - Swagger UI: `/docs`
    - ReDoc: `/redoc`
    """,
    version="1.0.0",
    contact={
        "name": "BV Support",
        "email": "support@bv.fr",
    },
    license_info={
        "name": "Propriétaire - BV",
    },
    lifespan=lifespan  # Gestion du cycle de vie
)


# ============================================================
# CONFIGURATION CORS
# ============================================================

# CORS permet au frontend (Next.js) de communiquer avec l'API
# Même si le frontend est sur un port différent (3000 vs 8000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# INCLUSION DES ROUTES
# ============================================================

# Inclure les routes d'authentification
app.include_router(auth.router)

# Inclure les routes de gestion des utilisateurs
app.include_router(users.router)
app.include_router(chat_router)
app.include_router(chat_history_router)

# Interface de test
_UI_PATH = Path(__file__).parent / "static" / "chat.html"

@app.get("/ui", response_class=HTMLResponse, tags=["UI"])
def chat_ui():
    """Interface de test minimale pour le pipeline."""
    if not _UI_PATH.exists():
        return HTMLResponse("Interface non trouvée.", status_code=404)
    return HTMLResponse(_UI_PATH.read_text(encoding="utf-8"))


# ============================================================
# ROUTES DE BASE
# ============================================================

@app.get(
    "/",
    tags=["Health"],
    summary="Vérification de l'état de l'API",
    description="Endpoint simple pour vérifier que l'API est opérationnelle."
)
async def root():
    """
    Endpoint racine pour vérifier que l'API fonctionne.
    
    Retourne:
    - **status**: "ok"
    - **message**: Message de bienvenue
    - **version**: Version de l'API
    """
    return {
        "status": "ok",
        "message": "Bienvenue sur l'API BV Auth Backend",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/auth",
            "users": "/users",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Endpoint pour les vérifications de santé (monitoring)."
)
async def health_check():
    """
    Health check pour les systèmes de monitoring.
    """
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# GESTIONNAIRE D'EXCEPTIONS GLOBAL
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Gère les exceptions HTTP de manière uniforme.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Gère toutes les exceptions non capturées.
    """
    logger.error(f"Exception non gérée: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Une erreur interne est survenue",
            "status_code": 500,
            "path": request.url.path
        }
    )


# INFORMATION SUR L'APPLICATION (optionnel)

@app.get("/info", tags=["Info"])
async def get_info():
    """
    Retourne des informations sur l'application.
    """
    from app.models.user import UserRole
    
    return {
        "name": "BV Auth Backend",
        "version": "1.0.0",
        "available_roles": [r.value for r in UserRole],
    }


# ============================================================
# SI LE SCRIPT EST EXÉCUTÉ DIRECTEMENT
# ============================================================

if __name__ == "__main__":
    """
    Démarrage du serveur en mode développement.
    
    Pour démarrer l'API:
    python -m app.main
    ou
    uvicorn app.main:app --reload
    """
    import uvicorn
    
    print("\n" + "=" * 60)
    print("🚀 DÉMARRAGE DU SERVEUR BV AUTH BACKEND")
    print("=" * 60)
    print(f"📡 API: http://{settings.HOST}:{settings.PORT}")
    print(f"📚 Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"📖 ReDoc: http://{settings.HOST}:{settings.PORT}/redoc")
    print("=" * 60)
    print("\n⚠️  Mode développement - Ne pas utiliser en production")
    print("   Pour arrêter: Ctrl+C\n")
    
    # Démarrer le serveur
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )