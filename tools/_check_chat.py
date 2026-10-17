import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("d:/PH/backend").resolve()))
from app.llm.intents import match

d = json.loads(Path("d:/PH/evaluation-dataset.json").read_text(encoding="utf-8"))
cases = d["chat_intents"]
ok = 0
for c in cases:
    pq = match(c["question"])
    intent_ok = pq.intent == c["expected_intent"]
    exp_ent = c.get("expected_entity")
    ent_ok = pq.entity == exp_ent
    flag = "OK " if (intent_ok and ent_ok) else "XX "
    if intent_ok and ent_ok:
        ok += 1
    print(flag, c["id"], "intent", pq.intent, "exp", c["expected_intent"],
          "| ent", repr(pq.entity), "exp", repr(exp_ent))
print(f"{ok}/{len(cases)}")