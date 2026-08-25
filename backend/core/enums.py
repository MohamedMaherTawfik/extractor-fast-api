"""Shared domain values used across schemas, models, and services."""

from enum import StrEnum


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TELEGRAM = "telegram"
    X = "x"
    WEBSITE = "website"
    OTHER = "other"


class AccessStatus(StrEnum):
    UNKNOWN = "unknown"
    ACCESSIBLE = "accessible"
    PRIVATE = "private"
    NOT_FOUND = "not_found"
    RESTRICTED = "restricted"
    ERROR = "error"


class ImportStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ContentType(StrEnum):
    VIDEO = "video"
    REEL = "reel"
    SHORT = "short"
    IMAGE = "image"
    CAROUSEL = "carousel"
    POST = "post"
    AUDIO = "audio"
    LIVE = "live"
    ARTICLE = "article"
    OTHER = "other"


class CollectionStatus(StrEnum):
    PENDING = "pending"
    COLLECTED = "collected"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    ANALYZING = "analyzing"
    NORMALIZING = "normalizing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AnalysisLevel(StrEnum):
    CONTENT = "content"
    SCENE = "scene"
    SEGMENT = "segment"
    SHOT = "shot"
    FRAME = "frame"
    AUDIO_EVENT = "audio_event"
    TEXT_EVENT = "text_event"
    VISUAL_EVENT = "visual_event"


class AnalysisResultStatus(StrEnum):
    ACCEPTED = "accepted"
    LOW_CONFIDENCE = "low_confidence"
    MANUAL_REVIEW = "manual_review"
    FAILED = "failed"


class AnalysisModality(StrEnum):
    METADATA = "metadata"
    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"
    AUDIO = "audio"
    TEXT = "text"


class AnalysisMode(StrEnum):
    FULL = "full"
    VISUAL_ONLY = "visual_only"
    AUDIO_ONLY = "audio_only"
    TEXT_ONLY = "text_only"


class ConnectorAvailability(StrEnum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    PERMISSION_REQUIRED = "permission_required"
    UNSUPPORTED = "unsupported"


class CollectionRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYING = "retrying"


class EvidenceType(StrEnum):
    OBSERVED = "observed"
    CORRELATED = "correlated"
    EXPERIMENTAL = "experimental"
    INFERRED = "inferred"


class TrafficType(StrEnum):
    ORGANIC = "organic"
    PAID = "paid"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PatternType(StrEnum):
    STRUCTURE = "structure_pattern"
    HOOK = "hook_pattern"
    VISUAL = "visual_pattern"
    EDITING = "editing_pattern"
    AUDIO = "audio_pattern"
    COPY = "copy_pattern"
    CTA = "cta_pattern"
    PRODUCT = "product_pattern"
    SEQUENCE = "sequence_pattern"
    TIMING = "timing_pattern"
    PERFORMANCE = "performance_pattern"
    CROSS_MODAL = "cross_modal_pattern"


class PatternStatus(StrEnum):
    STRUCTURAL = "structural_pattern"
    PERFORMANCE_ASSOCIATED = "performance_associated"
    LOW_CONFIDENCE = "low_confidence"


class PatternStability(StrEnum):
    NEW = "new"
    EMERGING = "emerging"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


class RecipeType(StrEnum):
    PROVEN_PATTERN = "proven_pattern"
    CREATOR_STYLE = "creator_style"
    PLATFORM_NATIVE = "platform_native"
    CATEGORY_TEMPLATE = "category_template"
    EXPERIMENTAL = "experimental"
    USER_DEFINED = "user_defined"
    HYBRID = "hybrid"


class RecipeStatus(StrEnum):
    PROVEN = "proven"
    EXPERIMENTAL = "experimental"
    DRAFT = "draft"
    INSUFFICIENT_DATA = "insufficient_data"


class RecipeCreatedBy(StrEnum):
    SYSTEM = "system"
    USER = "user"
    IMPORTED = "imported"


class RuleKind(StrEnum):
    HARD_CONSTRAINT = "hard_constraint"
    SOFT_CONSTRAINT = "soft_constraint"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    QA_GATE = "qa_gate"
    ACCESSIBILITY = "accessibility"
    BRAND = "brand"
    CHARACTER = "character"
    PLATFORM = "platform"
    RIGHTS = "rights"
    FACTUAL = "factual"
    AI_SAFETY = "ai_safety"
    RECIPE = "recipe"
    GENERATION = "generation"
    TECHNICAL = "technical"
    POLICY = "policy"


class RuleHardness(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class RuleSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleLifecycleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    DISABLED_UNDEFINED = "disabled_undefined"
    NON_EXECUTABLE = "non_executable"


class RuleAction(StrEnum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    REQUIRE_FIELD = "require_field"
    REQUIRE_EVIDENCE = "require_evidence"
    SET_CONSTRAINT = "set_constraint"
    SET_DEFAULT = "set_default"
    RECOMMEND = "recommend"
    REWRITE = "rewrite"
    RETRY = "retry"
    REGENERATE = "regenerate"
    HUMAN_REVIEW = "human_review"
    OMIT_FIELD = "omit_field"
    DOWNGRADE_CLAIM = "downgrade_claim"
    USE_FALLBACK = "use_fallback"
    DISABLE_FEATURE = "disable_feature"


class RuleResultStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    CONFLICT_REQUIRES_RESOLUTION = "conflict_requires_resolution"


class RuleEvaluationStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    HUMAN_REVIEW = "human_review"


class RuleScopeStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    PARTIAL_CONTEXT = "partial_context"


class TruthValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class RuleStage(StrEnum):
    PRE_ANALYSIS = "pre_analysis"
    POST_ANALYSIS = "post_analysis"
    PRE_PLAN = "pre_plan"
    POST_PLAN = "post_plan"
    POST_RECIPE = "post_recipe"
    PRE_GENERATION = "pre_generation"
    POST_GENERATION = "post_generation"
    PRE_PUBLISH = "pre_publish"
    POST_PERFORMANCE = "post_performance"


class RuleSourceType(StrEnum):
    MASTER_SHEET = "master_sheet"
    USER = "user"
    SYSTEM = "system"
    PLATFORM_PROFILE = "platform_profile"
    BRAND_PROFILE = "brand_profile"
    CHARACTER_PROFILE = "character_profile"
    LEGAL_POLICY = "legal_policy"
    ACCESSIBILITY_STANDARD = "accessibility_standard"
    GENERATED_DRAFT = "generated_draft"


class ControlClassification(StrEnum):
    PARAMETER = "parameter"
    CONSTRAINT = "constraint"
    VALIDATION_RULE = "validation_rule"
    POLICY = "policy"
    REFERENCE = "reference"
    GENERATION_GUIDANCE = "generation_guidance"
    QA_RULE = "qa_rule"
    ACCESSIBILITY_RULE = "accessibility_rule"
    PLATFORM_RULE = "platform_rule"
    BRAND_RULE = "brand_rule"
    CHARACTER_RULE = "character_rule"
    UNDEFINED = "undefined"
    INTEGRATION_ONLY = "integration_only"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RuleCommand(StrEnum):
    INGEST = "ingest"
    VALIDATE = "validate"
    ANALYZE = "analyze"
    PLAN = "plan"
    GENERATE = "generate"
    QA = "qa"
    PUBLISH = "publish"
    LEARN = "learn"


class GenerationJobStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PLANNING = "planning"
    GENERATING = "generating"
    PROCESSING = "processing"
    QA_PENDING = "qa_pending"
    QA_FAILED = "qa_failed"
    RETRY_PENDING = "retry_pending"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    COMPLETED_WITH_FALLBACK = "completed_with_fallback"


class GenerationType(StrEnum):
    TEXT = "text"
    COPY = "copy"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    IMAGE = "image"
    IMAGE_VARIATION = "image_variation"
    IMAGE_EDIT = "image_edit"
    VIDEO = "video"
    VIDEO_SHOT = "video_shot"
    VIDEO_SEQUENCE = "video_sequence"
    AUDIO = "audio"
    VOICE = "voice"
    SFX = "sfx"
    MUSIC_BRIEF = "music_brief"
    CAPTIONS = "captions"
    TRANSCRIPT = "transcript"
    AUDIO_DESCRIPTION_DRAFT = "audio_description_draft"
    MULTIMODAL_PACKAGE = "multimodal_package"


class GenerationPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProviderPreference(StrEnum):
    LOCAL_FIRST = "local_first"
    REMOTE_FIRST = "remote_first"
    BALANCED = "balanced"
    FORCE_LOCAL = "force_local"
    FORCE_REMOTE = "force_remote"


class ProviderLocality(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"


class ProviderAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class ReferenceRole(StrEnum):
    IDENTITY = "identity"
    POSE = "pose"
    EXPRESSION = "expression"
    WARDROBE = "wardrobe"
    HAIR = "hair"
    PRODUCT = "product"
    BACKGROUND = "background"
    LIGHTING = "lighting"
    COMPOSITION = "composition"
    COLOR = "color"
    MATERIAL = "material"
    CAMERA = "camera"
    STYLE_REFERENCE = "style_reference"


class QAResultStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class QACategory(StrEnum):
    TECHNICAL = "technical_qa"
    SCHEMA = "schema_qa"
    CHARACTER = "character_qa"
    PRODUCT = "product_qa"
    BRAND = "brand_qa"
    VISUAL = "visual_qa"
    COPY = "copy_qa"
    AUDIO = "audio_qa"
    ACCESSIBILITY = "accessibility_qa"
    RIGHTS = "rights_qa"
    PROVENANCE = "provenance_qa"
    CONTINUITY = "continuity_qa"


class GenerationRetryType(StrEnum):
    SAME_MODEL_RETRY = "same_model_retry"
    PROMPT_REPAIR = "prompt_repair"
    REFERENCE_ADJUSTMENT = "reference_adjustment"
    PARAMETER_CHANGE = "parameter_change"
    FALLBACK_MODEL = "fallback_model"
    HUMAN_REVIEW = "human_review"


class ReproducibilityLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    BEST_EFFORT = "best_effort"
    NON_DETERMINISTIC = "non_deterministic"


class GeneratedAssetStatus(StrEnum):
    DRAFT = "draft"
    QA_FAILED = "qa_failed"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    ARCHIVED = "archived"
