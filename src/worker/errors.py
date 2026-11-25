"""
BlastGate Worker Error Hierarchy
"""


class WorkerError(Exception):
    """Base exception for worker domain."""
    pass


class ProcessingStalledError(WorkerError):
    """Raised when worker processing loop experiences an unrecoverable stall."""
    pass


class HeartbeatEmissionError(WorkerError):
    """Raised when health supervisor fails to publish telemetry."""
    pass
