"""
BlastGate Worker Processing Loop
Simulates background queue processing workload.
Supports controlled processing stall simulation where container remains RUNNING but processing stops.
"""

import time
import threading
from typing import Optional


class WorkProcessor:
    """Simulates background job processing."""

    def __init__(self, interval_seconds: float = 2.0):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.is_stalled = False
        self.last_processed_timestamp = 0.0
        self.processed_count = 0
        self._stall_lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self):
        """Starts background processing thread."""
        self.is_running = True
        self.last_processed_timestamp = time.time()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops processing thread."""
        self.is_running = False
        self._stop_event.set()
        if hasattr(self, "_thread"):
            self._thread.join(timeout=2.0)

    def trigger_controlled_stall(self, reason: str = "Simulated memory leak / deadlock"):
        """
        Controlled failure injection for testing:
        Stalls processing loop while the container and health supervisor remain alive!
        """
        with self._stall_lock:
            self.is_stalled = True
            self._stall_reason = reason

    def reset_stall(self):
        """Recovers processing loop."""
        with self._stall_lock:
            self.is_stalled = False
            self.last_processed_timestamp = time.time()

    def _run_loop(self):
        while not self._stop_event.is_set():
            with self._stall_lock:
                if self.is_stalled:
                    # Stalled: Do NOT update last_processed_timestamp
                    time.sleep(self.interval_seconds)
                    continue

            # Healthy work execution
            self.processed_count += 1
            self.last_processed_timestamp = time.time()
            time.sleep(self.interval_seconds)

    @property
    def processing_age(self) -> float:
        """Seconds since last successful job execution."""
        if self.last_processed_timestamp == 0.0:
            return 0.0
        return time.time() - self.last_processed_timestamp
