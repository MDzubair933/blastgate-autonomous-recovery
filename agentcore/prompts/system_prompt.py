"""
BlastGate AgentCore System Prompt Loader
Exposes the versioned, authoritative system prompt for the BlastGate Managed Harness.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.txt"

VERSION: str = "1.0.0"


def load_system_prompt() -> str:
    """Loads the raw text of the BlastGate system prompt."""
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_harness_system_prompt_blocks() -> list:
    """Returns the system prompt formatted for the Boto3 CreateHarness API structure."""
    return [{"text": load_system_prompt()}]
