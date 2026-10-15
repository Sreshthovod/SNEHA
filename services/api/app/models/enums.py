"""Domain enumerations. Values are part of the API contract and stored in the database."""

from enum import StrEnum


class UserRole(StrEnum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    CLINICIAN = "clinician"
    ADMIN = "admin"


class AuthSessionKind(StrEnum):
    PASSWORD = "password"  # noqa: S105 - enum value; dashboard login (caregiver, clinician, admin)
    DEVICE = "device"  # paired patient device


class Language(StrEnum):
    """Languages SNEHA intends to support (ISO 639 codes).

    Voice support varies by language; see docs/ai-models.md.
    """

    ASSAMESE = "as"
    BENGALI = "bn"
    BODO = "brx"
    ENGLISH = "en"
    GARO = "grt"
    HINDI = "hi"
    KHASI = "kha"
    MANIPURI = "mni"
    MIZO = "lus"
    NAGAMESE = "nag"
    NEPALI = "ne"


class ConsentType(StrEnum):
    DATA_PROCESSING = "data_processing"  # store activity results and Memory Bank content
    CLINICIAN_SHARING = "clinician_sharing"  # let granted clinicians view data
    CLOUD_AI = "cloud_ai"  # send conversation text to an online AI provider
    VOICE_PROCESSING = "voice_processing"  # process speech audio


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


class ConsentGiver(StrEnum):
    PATIENT = "patient"
    LEGAL_REPRESENTATIVE = "legal_representative"
    CAREGIVER_ON_BEHALF = "caregiver_on_behalf"


class ActivityType(StrEnum):
    MEMORY_RECALL = "memory_recall"
    PICTURE_MATCHING = "picture_matching"
    WORD_ASSOCIATION = "word_association"
    SEQUENCING = "sequencing"
    ATTENTION = "attention"
    ORIENTATION = "orientation"
    REMINISCENCE = "reminiscence"
    OBJECT_RECOGNITION = "object_recognition"
    CATEGORIZATION = "categorization"


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SessionEndReason(StrEnum):
    COMPLETED = "completed"
    USER_STOPPED = "user_stopped"
    FATIGUE_DETECTED = "fatigue_detected"
    TIMEOUT = "timeout"


class RecordSource(StrEnum):
    DEVICE = "device"
    DASHBOARD = "dashboard"


class MemoryKind(StrEnum):
    PERSON = "person"
    PLACE = "place"
    EVENT = "event"
    OBJECT = "object"
    STORY = "story"


class MemoryStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryRelationType(StrEnum):
    RELATED_TO = "related_to"
    PERSON_IN = "person_in"
    LOCATED_AT = "located_at"
    PART_OF = "part_of"


class ObservationCategory(StrEnum):
    MOOD = "mood"
    SLEEP = "sleep"
    APPETITE = "appetite"
    ORIENTATION = "orientation"
    BEHAVIOUR = "behaviour"
    PHYSICAL = "physical"
    FATIGUE = "fatigue"
    OTHER = "other"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class FilePurpose(StrEnum):
    MEMORY_MEDIA = "memory_media"
    REPORT_PDF = "report_pdf"


class ConversationProviderUsed(StrEnum):
    DETERMINISTIC = "deterministic"
    GEMINI = "gemini"
    LOCAL = "local"  # optional self-hosted model (migration 0007)


class SyncEntity(StrEnum):
    ACTIVITY_SESSION = "activity_session"
    ACTIVITY_RESULT = "activity_result"
    CONVERSATION = "conversation"
    PERSONALIZATION_STATE = "personalization_state"
    MEMORY_ITEM = "memory_item"
    MEMORY_RELATIONSHIP = "memory_relationship"
    ROUTINE_ITEM = "routine_item"
    ACTIVITY_DEFINITION = "activity_definition"


class SyncOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class SyncMutationStatus(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class Engagement(StrEnum):
    """The patient's own (or a helper's) answer to "Did you enjoy this?"."""

    ENJOYED = "enjoyed"
    NEUTRAL = "neutral"
    NOT_ENJOYED = "not_enjoyed"


class RecommendationAction(StrEnum):
    ACTIVITY = "activity"  # play the recommended activity
    BREAK = "break"  # offer a rest; an easier alternative is attached
    STOP = "stop"  # the patient asked to stop: end now, recommend nothing
    NONE = "none"  # nothing suitable is available


class ObservationStatus(StrEnum):
    """Caregiver observation workflow: open → reviewed → resolved."""

    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
