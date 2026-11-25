"""
BlastGate Incident Ingestion Package
Provides incident models, repositories, deduplication engine, event validation, and handler.
"""

from .models import IncidentRecord
from .repository import IncidentRepository, MockIncidentRepository, DynamoDbIncidentRepository
from .deduplication import IncidentDeduplicator
from .validator import AlarmEventValidator
from .handler import lambda_handler

__all__ = [
    "IncidentRecord",
    "IncidentRepository",
    "MockIncidentRepository",
    "DynamoDbIncidentRepository",
    "IncidentDeduplicator",
    "AlarmEventValidator",
    "lambda_handler",
]
