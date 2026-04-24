from enum import Enum


class DocumentFileType(str, Enum):
    PDF = "pdf"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"


class BillExtractionStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class InsightType(str, Enum):
    TREND = "trend"
    ANOMALY = "anomaly"
    SEASONALITY = "seasonality"
    FORECAST = "forecast"
    GENERAL = "general"


class ExtractionLogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ExtractionLogStage(str, Enum):
    UPLOAD = "upload"
    TEXT_EXTRACTION = "text_extraction"
    NORMALIZATION = "normalization"
    SEMANTIC_PARSING = "semantic_parsing"
    VALIDATION = "validation"
    REVIEW = "review"

