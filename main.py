# main.py
from __future__ import annotations

import sys
import time
from pathlib import Path

from core.context import Context
from modules.expert import Expert

KB_DIR = Path("assets/knowledge").resolve()  # можно оставить пустым — Expert отработает и без базы


def run_smoke_test() -> bool:
    ctx = Context(
        discipline="Цифровая культура",
        lesson_number=1,
        topic="ИИ и цифровые продукты",
        student_level=1,
        mode="live",
        student_id="test#0001"
    )
    ctx.last_user_question = "Дай определение ИИ и пример применения."
    kb_path = str(KB_DIR) if KB_DIR.exists() else None
    expert = Expert(kb_path)
    result = expert.process(ctx)
    print("[SMOKE TEST] Answer:", result.get("answer", "")[:160], "...")
    print("[SMOKE TEST] Sources:", result.get("sources"))
    return True


if __name__ == "__main__":
    ok = run_smoke_test()
    print("✔ Test passed" if ok else "✖ Test failed")
    sys.exit(0 if ok else 1)