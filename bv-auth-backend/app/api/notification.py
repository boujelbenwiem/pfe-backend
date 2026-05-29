from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.services.email_service import EmailService
from app.core.config import settings
from app.core.deps import get_current_user


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/send-email")
async def send_email(to_address: str, subject: str, body: str, current_user: str = Depends(get_current_user)):
    email_service = EmailService()
    success = email_service.send_email(to_address, subject, body)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de l'envoi de l'email")
    return {"message": "Email envoyé avec succès"}
