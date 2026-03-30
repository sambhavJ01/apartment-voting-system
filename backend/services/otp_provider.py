"""
OTP Provider abstraction layer.

To add a new WhatsApp provider:
  1. Subclass OTPProvider
  2. Implement send_otp()
  3. Handle instantiation in get_otp_provider()

No other code needs to change.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class OTPProvider(ABC):
    """Abstract interface for WhatsApp OTP delivery."""

    @abstractmethod
    def send_otp(self, phone_number: str, otp: str, purpose: str) -> bool:
        """
        Deliver the OTP to the given phone number via WhatsApp.

        Args:
            phone_number: Recipient in E.164 format, e.g. +919876543210
            otp:          The 6-digit code to deliver
            purpose:      'registration' | 'login' | 'vote_confirmation'

        Returns:
            True on success, False on failure.
        """


# ─── Console (development) ────────────────────────────────────────────────────

class ConsoleOTPProvider(OTPProvider):
    """Prints OTP to stdout. Use ONLY during local development."""

    def send_otp(self, phone_number: str, otp: str, purpose: str) -> bool:
        border = "=" * 55
        print(f"\n{border}")
        print(f"  [DEV OTP]  Purpose : {purpose}")
        print(f"             Phone   : {phone_number}")
        print(f"             OTP     : {otp}")
        print(f"{border}\n")
        logger.info("Console OTP | %s | %s | %s", purpose, phone_number, otp)
        return True


# ─── Twilio WhatsApp ──────────────────────────────────────────────────────────

class TwilioOTPProvider(OTPProvider):
    """Sends OTP via Twilio WhatsApp Business API."""

    _PURPOSE_LABELS = {
        "registration": "verify your registration",
        "login": "log in securely",
        "vote_confirmation": "confirm your vote",
    }

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        try:
            from twilio.rest import Client
            self._client = Client(account_sid, auth_token)
            self._from = from_number  # e.g. "whatsapp:+14155238886"
        except ImportError:
            raise RuntimeError("Twilio is not installed — run: pip install twilio")

    def send_otp(self, phone_number: str, otp: str, purpose: str) -> bool:
        action = self._PURPOSE_LABELS.get(purpose, "complete your action")
        body = (
            f"🔐 Your Apartment Voting System OTP is: *{otp}*\n"
            f"Use this to {action}. Expires in 5 minutes.\n"
            f"Do NOT share this code with anyone."
        )
        try:
            msg = self._client.messages.create(
                body=body,
                from_=self._from,
                to=f"whatsapp:{phone_number}",
            )
            logger.info("Twilio OTP sent | %s | SID=%s", phone_number, msg.sid)
            return True
        except Exception as exc:
            logger.error("Twilio send failed | %s | %s", phone_number, exc)
            return False


# ─── Gupshup WhatsApp ─────────────────────────────────────────────────────────

class GupshupOTPProvider(OTPProvider):
    """Sends OTP via Gupshup WhatsApp API."""

    def __init__(self, api_key: str, app_name: str, src_name: str) -> None:
        self._api_key = api_key
        self._app_name = app_name
        self._src_name = src_name

    def send_otp(self, phone_number: str, otp: str, purpose: str) -> bool:
        import httpx

        payload = {
            "channel": "whatsapp",
            "source": self._src_name,
            "destination": phone_number,
            "src.name": self._app_name,
            "message": {
                "type": "text",
                "text": (
                    f"Your OTP for {purpose} (Apartment Voting) is: {otp}. "
                    f"Valid for 5 minutes."
                ),
            },
        }
        headers = {"apikey": self._api_key, "Content-Type": "application/json"}
        try:
            resp = httpx.post(
                "https://api.gupshup.io/sm/api/v1/msg",
                json=payload, headers=headers, timeout=10,
            )
            resp.raise_for_status()
            logger.info("Gupshup OTP sent | %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Gupshup send failed | %s | %s", phone_number, exc)
            return False


# ─── Meta WhatsApp Cloud API ──────────────────────────────────────────────────

class MetaWhatsAppOTPProvider(OTPProvider):
    """Sends OTP via Meta (Facebook) WhatsApp Cloud API using a message template."""

    def __init__(
        self,
        phone_number_id: str,
        access_token: str,
        template_name: str = "otp_template",
    ) -> None:
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._template_name = template_name

    def send_otp(self, phone_number: str, otp: str, purpose: str) -> bool:
        import httpx

        url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": self._template_name,
                "language": {"code": "en_US"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": otp}],
                    }
                ],
            },
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info("Meta OTP sent | %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Meta send failed | %s | %s", phone_number, exc)
            return False


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_otp_provider(settings) -> OTPProvider:
    """Instantiate and return the configured OTP provider."""
    name = settings.OTP_PROVIDER.lower()

    if name == "console":
        return ConsoleOTPProvider()

    if name == "twilio":
        missing = [
            k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
            if not getattr(settings, k)
        ]
        if missing:
            raise RuntimeError(f"Twilio provider is missing config: {missing}")
        return TwilioOTPProvider(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_WHATSAPP_FROM,
        )

    if name == "gupshup":
        missing = [
            k for k in ("GUPSHUP_API_KEY", "GUPSHUP_APP_NAME", "GUPSHUP_SRC_NAME")
            if not getattr(settings, k)
        ]
        if missing:
            raise RuntimeError(f"Gupshup provider is missing config: {missing}")
        return GupshupOTPProvider(
            settings.GUPSHUP_API_KEY,
            settings.GUPSHUP_APP_NAME,
            settings.GUPSHUP_SRC_NAME,
        )

    if name == "meta":
        missing = [
            k for k in ("META_PHONE_NUMBER_ID", "META_ACCESS_TOKEN")
            if not getattr(settings, k)
        ]
        if missing:
            raise RuntimeError(f"Meta WhatsApp provider is missing config: {missing}")
        return MetaWhatsAppOTPProvider(
            settings.META_PHONE_NUMBER_ID,
            settings.META_ACCESS_TOKEN,
            settings.META_OTP_TEMPLATE_NAME,
        )

    logger.warning("Unknown OTP provider %r — falling back to ConsoleOTPProvider", name)
    return ConsoleOTPProvider()
