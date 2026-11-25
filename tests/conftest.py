"""
Pytest configuration for BlastGate test suite.
Configures python search paths and unifies broker module namespaces.
"""

import sys
import importlib
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HACKATHON_ROOT = TESTS_DIR.parent
SRC_DIR = HACKATHON_ROOT / "src"
BROKER_DIR = SRC_DIR / "broker"

for p in [str(BROKER_DIR), str(SRC_DIR), str(HACKATHON_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Unify sys.modules so `broker.X` and `X` resolve to identical module instances
BROKER_MODULES = [
    "config", "errors", "models", "catalog", "inventory",
    "capacity", "budget", "idempotency", "executor", "audit",
    "recovery", "authorization", "handler"
]

for mod_name in BROKER_MODULES:
    mod = importlib.import_module(mod_name)
    sys.modules[f"broker.{mod_name}"] = mod
