import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class NotificationService:
    """Base service for handling notifications."""
    def __init__(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    async def notify(self, message: str, payload: Dict[str, Any] = None):
        if not self.enabled:
            return
        await self._send(message, payload)

    async def _send(self, message: str, payload: Dict[str, Any] = None):
        raise NotImplementedError("Subclasses must implement _send")

class EmailNotificationService(NotificationService):
    """Sends notifications via email."""
    async def _send(self, message: str, payload: Dict[str, Any] = None):
        # Placeholder for email sending logic (e.g., using SMTP or an API)
        logger.info(f"[EMAIL] Sending: {message} | Payload: {payload}")

class DiscordNotificationService(NotificationService):
    """Sends notifications via Discord Webhooks."""
    async def _send(self, message: str, payload: Dict[str, Any] = None):
        # Placeholder for Discord webhook logic
        logger.info(f"[DISCORD] Sending: {message} | Payload: {payload}")

# Singleton instances
email_service = EmailNotificationService()
discord_service = DiscordNotificationService()

# Registry for easy access to enabled services
services = {
    "email": email_service,
    "discord": discord_service
}

def enable_service(name: str):
    if name in services:
        services[name].enable()
