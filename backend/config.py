import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Apartment Voting System"
    DEBUG: bool = False

    # Database — swap URL for PostgreSQL/MySQL without changing any other code
    DATABASE_URL: str = "sqlite:///./voting_system.db"

    # JWT
    SECRET_KEY: str = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OTP
    OTP_SECRET_SALT: str = "CHANGE_THIS_OTP_SALT_IN_PRODUCTION"
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_RETRIES: int = 3
    OTP_RATE_LIMIT_SECONDS: int = 60  # minimum seconds between OTP requests

    # Anonymous voting — deterministic hash salt; never change once data exists
    ANON_VOTE_SALT: str = "CHANGE_THIS_ANON_SALT_IN_PRODUCTION"

    # Admin bootstrap
    ADMIN_REGISTRATION_KEY: str = "ADMIN_SECRET_CHANGE_THIS"

    # OTP provider: console | twilio | gupshup | meta
    OTP_PROVIDER: str = "console"

    # Twilio
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = "whatsapp:+14155238886"

    # Gupshup
    GUPSHUP_API_KEY: Optional[str] = None
    GUPSHUP_APP_NAME: Optional[str] = None
    GUPSHUP_SRC_NAME: Optional[str] = None

    # Meta WhatsApp Cloud API
    META_PHONE_NUMBER_ID: Optional[str] = None
    META_ACCESS_TOKEN: Optional[str] = None
    META_OTP_TEMPLATE_NAME: str = "otp_template"

    # Streamlit points here
    BACKEND_URL: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
