"""
Envoi d'e-mails transactionnels (Flash Neiga).

Sert aujourd'hui à une seule chose, mais elle est légale : remettre sa facture
au client, à chaque paiement et à chaque renouvellement.

Le transport est un simple serveur SMTP, configuré par variables
d'environnement — n'importe quel fournisseur convient (Gmail Workspace, Brevo,
Resend, OVH, Mailgun…) :

    SMTP_HOST       smtp-relay.brevo.com
    SMTP_PORT       587            (465 = SSL direct, 587 = STARTTLS)
    SMTP_USER       identifiant
    SMTP_PASSWORD   mot de passe / clé SMTP
    SMTP_FROM       "Flash Neiga <factures@flash-neiga.com>"
    SMTP_REPLY_TO   (facultatif) adresse de réponse
    SMTP_BCC        (facultatif) copie cachée, par ex. la comptable

Sans SMTP_HOST, rien n'est envoyé : la facture reste émise, téléchargeable
depuis le profil de l'élève, et l'envoi sera retenté dès que le serveur SMTP
sera renseigné.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Iterable, Optional, Tuple

logger = logging.getLogger(__name__)


class MailNotConfigured(Exception):
    """Aucun serveur SMTP n'est renseigné."""


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def configured() -> bool:
    return bool(_env("SMTP_HOST"))


def sender() -> str:
    """Adresse d'expédition. À défaut de SMTP_FROM, l'identifiant SMTP."""
    return _env("SMTP_FROM") or _env("SMTP_USER")


def status() -> dict:
    """État de la configuration, sans jamais exposer le mot de passe."""
    return {
        "configured": configured(),
        "host": _env("SMTP_HOST") or None,
        "port": int(_env("SMTP_PORT", "587") or 587),
        "sender": sender() or None,
        "bcc": _env("SMTP_BCC") or None,
    }


def send(
    to: str,
    subject: str,
    text: str,
    html: Optional[str] = None,
    attachments: Iterable[Tuple[str, bytes, str]] = (),
    timeout: int = 20,
) -> str:
    """Envoie un message et renvoie son Message-ID.

    `attachments` : tuples (nom de fichier, contenu, type MIME).
    Lève MailNotConfigured sans SMTP_HOST, et laisse remonter les erreurs SMTP :
    c'est à l'appelant de décider s'il retente.
    """
    host = _env("SMTP_HOST")
    if not host:
        raise MailNotConfigured("SMTP_HOST n'est pas renseigné")
    port = int(_env("SMTP_PORT", "587") or 587)
    user = _env("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD") or ""
    from_addr = sender()
    if not from_addr:
        raise MailNotConfigured("SMTP_FROM (ou SMTP_USER) n'est pas renseigné")

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    reply_to = _env("SMTP_REPLY_TO")
    if reply_to:
        msg["Reply-To"] = reply_to
    domain = (parseaddr(from_addr)[1].rpartition("@")[2]) or None
    msg["Message-ID"] = make_msgid(domain=domain)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, content, mime in attachments:
        maintype, _, subtype = (mime or "application/octet-stream").partition("/")
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    recipients = [to]
    bcc = _env("SMTP_BCC")
    if bcc:
        recipients += [a.strip() for a in bcc.split(",") if a.strip()]

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            if user:
                smtp.login(user, password)
            smtp.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=context)
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg, to_addrs=recipients)

    logger.info("E-mail « %s » envoyé à %s", subject, to)
    return msg["Message-ID"]


def display_name(name: Optional[str], email: str) -> str:
    return formataddr((name, email)) if name else email
