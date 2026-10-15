"""Import every ORM model here so Alembic autogenerate can see the full metadata."""

from app.db.base import Base
from app.models.activities import (
    ActivityDefinition,
    ActivityRecommendation,
    ActivityResult,
    ActivitySession,
    PersonalizationState,
)
from app.models.care import (
    CaregiverObservation,
    ConversationRecord,
    ObservationRevision,
    Report,
    RoutineItem,
)
from app.models.files import StoredFile
from app.models.memories import MemoryItem, MemoryRelationship
from app.models.patients import (
    CaregiverRelationship,
    ClinicianAccessGrant,
    ConsentRecord,
    DevicePairingCode,
    PatientPreferences,
    PatientProfile,
)
from app.models.sync import AuditEvent, SyncChange, SyncMutation
from app.models.users import AuthSession, User

__all__ = [
    "ActivityDefinition",
    "ActivityRecommendation",
    "ActivityResult",
    "ActivitySession",
    "AuditEvent",
    "AuthSession",
    "Base",
    "CaregiverObservation",
    "CaregiverRelationship",
    "ClinicianAccessGrant",
    "ConsentRecord",
    "ConversationRecord",
    "DevicePairingCode",
    "MemoryItem",
    "MemoryRelationship",
    "ObservationRevision",
    "PatientPreferences",
    "PatientProfile",
    "PersonalizationState",
    "Report",
    "RoutineItem",
    "StoredFile",
    "SyncChange",
    "SyncMutation",
    "User",
]
