import os, subprocess
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
subprocess.run([str(root / ".venv/Scripts/ruff.exe"), "format", str(root), "-q"])
