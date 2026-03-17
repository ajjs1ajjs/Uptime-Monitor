import ssl
import socket
from datetime import datetime, timedelta
from urllib.parse import urlparse
import asyncio
import aiohttp

async def check_ssl_certificate(url: str):
    """Перевіряє SSL сертифікат сайту"""
    try:
        # Парсимо URL
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443
        
        if not hostname:
            return None
        
        # Створюємо SSL контекст
        context = ssl.create_default_context()
        
        # Отримуємо сертифікат
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                if not cert:
                    return None
                
                # Парсимо дати
                not_after = cert.get('notAfter')
                not_before = cert.get('notBefore')
                
                if not_after:
                    # Конвертуємо дату закінчення
                    expire_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    
                    # Конвертуємо дату початку
                    start_date = datetime.strptime(not_before, '%b %d %H:%M:%S %Y %Z') if not_before else None
                    
                    # Розраховуємо дні до закінчення
                    days_until_expire = (expire_date - datetime.utcnow()).days
                    
                    # Отримуємо issuer
                    issuer = cert.get('issuer', [])
                    issuer_str = ', '.join(['='.join(x[0]) for x in issuer]) if issuer else 'Unknown'
                    
                    # Отримуємо subject
                    subject = cert.get('subject', [])
                    subject_str = ', '.join(['='.join(x[0]) for x in subject]) if subject else 'Unknown'
                    
                    return {
                        'hostname': hostname,
                        'subject': subject_str,
                        'issuer': issuer_str,
                        'start_date': start_date.isoformat() if start_date else None,
                        'expire_date': expire_date.isoformat(),
                        'days_until_expire': days_until_expire,
                        'is_valid': days_until_expire > 0,
                        'checked_at': datetime.now().isoformat()
                    }
        
        return None
    except Exception as e:
        print(f"SSL check error for {url}: {e}")
        return None

def should_notify_certificate(days_until_expire: int, last_notified_days: int = None):
    """
    Визначає чи треба сповіщати про сертифікат
    Сповіщати за 14 днів, потім кожен день
    """
    if days_until_expire > 14:
        return False
    
    if days_until_expire <= 0:
        return True
    
    return True

def format_certificate_alert(cert_info: dict, site_name: str, site_url: str):
    """Форматує повідомлення про сертифікат"""
    days = cert_info['days_until_expire']
    expire_date = datetime.fromisoformat(cert_info['expire_date']).strftime('%Y-%m-%d %H:%M')
    
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
