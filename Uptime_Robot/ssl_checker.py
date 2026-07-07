import asyncio
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from .logger import logger


def _check_ssl_certificate_sync(url: str):
    """Перевіряє SSL сертифікат сайту (синхронно).

    Uses CERT_NONE so the handshake completes (and the certificate can still
    be read) even when it's expired, self-signed, or otherwise fails
    validation — the point of this check is to REPORT those problems, not to
    silently disappear the site from the SSL list because of them. Cert
    fields are pulled from the raw DER cert via `cryptography`, since
    ssl.SSLSocket.getpeercert() returns an empty dict when verification is
    disabled instead of populating notAfter/notBefore/issuer/subject.
    """
    from cryptography import x509

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443

        if not hostname:
            return None

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)

        if not der_cert:
            return None

        cert = x509.load_der_x509_certificate(der_cert)
        expire_date = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(
            tzinfo=timezone.utc
        )
        start_date = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(
            tzinfo=timezone.utc
        )
        days_until_expire = (expire_date - datetime.now(timezone.utc)).days

        return {
            "hostname": hostname,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "start_date": start_date.isoformat(),
            "expire_date": expire_date.isoformat(),
            "days_until_expire": days_until_expire,
            "is_valid": days_until_expire > 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("SSL check error for %s: %s", url, e)
        return None


async def check_ssl_certificate(url: str):
    """Перевіряє SSL сертифікат сайту (асинхронно через пул потоків)"""
    return await asyncio.to_thread(_check_ssl_certificate_sync, url)


def format_certificate_alert(cert_info: dict, site_name: str, site_url: str):
    """Форматує повідомлення про сертифікат"""
    days = cert_info["days_until_expire"]
    expire_date = datetime.fromisoformat(cert_info["expire_date"]).strftime("%Y-%m-%d %H:%M")

    if days <= 0:
        icon = "🔴"
        status = "ПРОСТРОЧЕНИЙ"
        urgency = "КРИТИЧНО"
    elif days <= 3:
        icon = "🔴"
        status = f"Закінчується через {days} днів"
        urgency = "КРИТИЧНО"
    elif days <= 7:
        icon = "🟠"
        status = f"Закінчується через {days} днів"
        urgency = "ВАЖЛИВО"
    else:
        icon = "🟡"
        status = f"Закінчується через {days} днів"
        urgency = "УВАГА"

    message = f"""{icon} SSL Сертифікат - {urgency}

🏢 Сайт: {site_name}
🌐 URL: {site_url}
📅 Статус: {status}
⏰ Дата закінчення: {expire_date}
🔒 Видавець: {cert_info['issuer']}
📋 Subject: {cert_info['subject']}

⚠️ Необхідно оновити сертифікат!"""

    return message
