"""One-off: inventory utility-class tokens used across frontend/src (to size the design-token CSS layer)."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "src"
pattern = re.compile(r'["\'`]([^"\'`]*)["\'`]')
token_like = re.compile(
    r"^(bg-|text-|border|rounded|px-|py-|pt-|pb-|pl-|pr-|p-|m-|mt-|gap-|flex|grid|items-|justify-|"
    r"w-|h-|min-|max-|font-|shadow|hover:|focus:|active:|disabled:|animate-|space-|sr-only|absolute|"
    r"relative|fixed|hidden|overflow-|leading-|tracking-|uppercase|lowercase|cursor-|transition|"
    r"opacity-|whitespace-|truncate|divide-|ring|top-|bottom-|left-|right-|z-|col-|row-|backdrop|"
    r"odd:|even:|first:|last:|group-hover|placeholder:|aria-)"
)

tokens: set[str] = set()
for f in root.rglob("*"):
    if f.suffix not in {".ts", ".tsx"} or f.name.endswith(".test.ts") or f.name.endswith(".test.tsx"):
        continue
    for m in pattern.finditer(f.read_text(encoding="utf-8")):
        for word in m.group(1).split():
            if token_like.match(word):
                tokens.add(word)

print(f"COUNT={len(tokens)}")
print("\n".join(sorted(tokens)))
