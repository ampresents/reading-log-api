import json, os, subprocess, sys
from pathlib import Path

sys.stderr.reconfigure(encoding="utf-8")
if json.load(sys.stdin.buffer).get("stop_hook_active"):
    sys.exit(0)  # 再開は1回まで(無限ループ防止)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
r = subprocess.run(
    [str(root / ".venv/Scripts/python.exe"), "-m", "pytest", "-q"],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
if r.returncode != 0:
    print("テストが失敗しています。修正してから終了してください", file=sys.stderr)
    print(r.stdout[-2000:], file=sys.stderr)
    sys.exit(2)
