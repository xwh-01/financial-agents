import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-python"
sys.path.insert(0, str(AGENT_ROOT))
