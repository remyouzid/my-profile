"""Send applications by e-mail through Gmail SMTP (app password)."""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email(smtp_cfg: dict, to: str, subject: str, body: str, attachments: list[Path] = ()) -> None:
    password = os.getenv(smtp_cfg["password_env"])
    if not password:
        raise RuntimeError(
            f"Variable {smtp_cfg['password_env']} manquante : crée un mot de passe d'application Gmail "
            "(myaccount.google.com/apppasswords) et exporte-le."
        )

    msg = EmailMessage()
    msg["From"] = smtp_cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachments:
        subtype = "pdf" if path.suffix.lower() == ".pdf" else "octet-stream"
        msg.add_attachment(path.read_bytes(), maintype="application", subtype=subtype, filename=path.name)

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
        server.starttls()
        server.login(smtp_cfg["user"], password)
        server.send_message(msg)
