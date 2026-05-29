import boto3

from app.core.config import settings

class EmailService:
    def __init__(self):
        self.client = boto3.client(
            "ses",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Envoie un email via AWS SES."""
        try:
            response = self.client.send_email(
                Source=settings.SES_FROM_EMAIL,
                Destination={"ToAddresses": [to_address]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )
            return response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except Exception as e:
            print(f"Erreur envoi email: {e}")
            return False

    def send_user_invitation_email(self, to_address: str, username: str, reset_token: str) -> bool:
        """Envoie un email d'invitation avec un lien pour définir le mot de passe."""
        # Construire le lien pour définir le mot de passe
        setup_url = f"{settings.FRONTEND_URL}/setup-password?token={reset_token}"
        
        subject = "Invitation - Définissez votre mot de passe"
        
        body = f"""Bienvenue {username},

Vous avez été invité à rejoindre BV. Pour accéder à l'application, cliquez sur le lien ci-dessous pour définir votre mot de passe :

{setup_url}

Ce lien sera valide pendant 24 heures.

Cordialement,
L'équipe BV"""
        
        return self.send_email(to_address, subject, body)
        