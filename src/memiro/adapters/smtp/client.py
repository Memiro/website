import smtplib
import ssl

from memiro.adapters.smtp.config import EmailConfig, SMTPEncryption


def smtp_client(config: EmailConfig) -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Open SMTP using the encryption mode selected by configuration."""
    if config.encryption is SMTPEncryption.SSL:
        return smtplib.SMTP_SSL(
            config.host, config.port, timeout=config.timeout_seconds, context=ssl.create_default_context()
        )
    client = smtplib.SMTP(config.host, config.port, timeout=config.timeout_seconds)
    if config.encryption is SMTPEncryption.STARTTLS:
        client.starttls(context=ssl.create_default_context())
    return client
