import json, os, re, subprocess, sys
from pathlib import Path

sys.stderr.reconfigure(encoding="utf-8")
data = json.load(sys.stdin.buffer)
tool = data.get("tool_name", "")
inp = data.get("tool_input", {})
root = os.environ.get("CLAUDE_PROJECT_DIR", ".")


def block(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


if tool == "Bash":
    if re.search(r"(^|[\s/\\\"'])\.env\b", inp.get("command", "")):
        block(".env を操作するコマンドは禁止です。変更はユーザーに依頼してください")
    sys.exit(0)

path = Path(inp.get("file_path", ""))
if path.name.startswith(".env"):
    block(".env は編集禁止です。変更はユーザーに依頼してください")

if "migrations" in path.parts and path.exists():
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)], cwd=root, capture_output=True
    )
    if r.returncode == 0:
        block(
            "コミット済みのマイグレーションは編集禁止です。新しいリビジョンを作ってください"
        )
