"""One-off: normalize hook line endings to LF and widen lint-staged glob."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]

for rel in (".husky/pre-commit", ".husky/commit-msg"):
    p = root / rel
    data = p.read_bytes().replace(b"\r\n", b"\n")
    p.write_bytes(data)
    print(f"{rel}: {'LF ok' if b'\\r' not in data else 'STILL CRLF'}")

rc = root / "frontend" / ".lintstagedrc"
text = rc.read_text(encoding="utf-8").replace("\r\n", "\n").replace('"*.{ts,tsx}"', '"**/*.{ts,tsx}"')
rc.write_text(text, encoding="utf-8", newline="")
print("lintstagedrc:", text.strip())
