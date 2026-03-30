# Import all models here so Base.metadata discovers every table.
from backend.models.apartment import Apartment       # noqa: F401
from backend.models.user import User, UserStatus     # noqa: F401
from backend.models.otp import OTPLog                # noqa: F401
from backend.models.topic import Topic, Option, VotingMode, TopicStatus  # noqa: F401
from backend.models.vote import Vote, VoteTracking   # noqa: F401
from backend.models.audit import AuditLog            # noqa: F401
