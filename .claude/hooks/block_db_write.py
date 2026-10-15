import sys

sys.stderr.reconfigure(encoding="utf-8")
print("DBへの直接書き込みは禁止です。APIを使ってください", file=sys.stderr)
sys.exit(2)
