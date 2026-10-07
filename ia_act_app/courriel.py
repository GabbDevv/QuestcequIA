"""Envoi des e-mails (invitations et rapport).

Facultatif : sans variable SMTP_HOST, rien n'est envoyé et l'application
affiche les liens de questionnaire à copier, ce qui suffit pour tester.

Variables d'environnement : SMTP_HOST, SMTP_PORT (587 par défaut), SMTP_USER,
SMTP_PASSWORD, SMTP_FROM.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def smtp_configure() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def envoyer(destinataire: str, sujet: str, corps: str) -> bool:
    """Envoie un e-mail en texte brut. Renvoie True si l'envoi a réussi."""
    if not smtp_configure():
        return False
    utilisateur = os.getenv("SMTP_USER", "")
    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", utilisateur)
    message["To"] = destinataire
    message["Subject"] = sujet
    message.set_content(corps)
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls()
            if utilisateur:
                smtp.login(utilisateur, os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError):
        return False


def envoyer_invitation(invitation: dict, projet: dict, lien: str) -> bool:
    corps = (
        f"Bonjour {invitation['prenom']},\n\n"
        f"Vous êtes invité(e) à répondre au questionnaire IA Act du projet "
        f"« {projet['nom']} ».\n\n"
        f"Questionnaire : {lien}\n\n"
        "Merci."
    )
    return envoyer(invitation["email"], f"Questionnaire IA Act : {projet['nom']}", corps)


def envoyer_rapport(invitation: dict, projet: dict, rapport_md: str) -> bool:
    corps = f"Bonjour {invitation['prenom']},\n\nLe rapport IA Act du projet a été émis.\n\n{rapport_md}"
    return envoyer(invitation["email"], f"Rapport IA Act : {projet['nom']}", corps)
