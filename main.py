# main.py

from typing import Optional
from core.context import Context
from core.fsm import TeachingFSM
from core.event_bus import EventBus
from core.conductor import Conductor
from modules.expert import Expert
from modules.motivator import Motivator
from modules.organizer import Organizer
from modules.cartographer import Cartographer

FACT_TRIGGERS = ["это", "называется", "является", "определяется как"]
PROCEDURE_TRIGGERS = ["сделайте", "выполните", "используйте", "шаг", "процесс", "алгоритм", "нужно"]
META_TRIGGERS = ["оцените", "сравните", "выберите", "зачем", "почему", "что лучше", "преимущество"]

REFLECTION_QUESTIONS = [
    "Что тебе мешает двигаться дальше?",
    "Есть ли момент, который вызывает сомнение?",
    "Как думаешь, чего сейчас не хватает для уверенности?",
    "Хочешь, мы попробуем упростить задачу?"
]

def observe(self, event: str, context: Context, question: Optional[str]=None, answer: Optional[dict]=None) -> dict:
#     """
#     Доработанный observe:
#     - аккуратно вычисляет латентность даже при "ручных" паузах;
#     - задаёт приоритет сценариев: frustration > low_metrics > slow_response > short_replies;
#     - объединяет результат _evaluate (S-уровень) с реакциями 6.2.
#     """
    # 0) базовые слоты и метрики
    slot = self._ensure_slot(context)
    ex = context.progress.get("Expert", {})
    now = time.time()

    # 1) собственная оценка латентности (на случай когда Expert не успел/не смог обновить avg)
    prev_seen = slot.get("last_seen_ts")
    computed_latency = max(0.0, now - prev_seen) if prev_seen else None
    slot["last_seen_ts"] = now

    # заберём метрики из Expert
    engagement = float(ex.get("engagement", 0.5))
    confidence = float(ex.get("confidence", 0.5))
    latency_sec = ex.get("latency_sec", computed_latency or 0.0)
    latency_avg = ex.get("latency_avg_sec", None)

    # если avg отсутствует или равен 0 — используем вычисленное значение
    if latency_avg is None or latency_avg == 0.0:
        latency_avg = max(latency_sec, computed_latency or 0.0)
        ex["latency_avg_sec"] = latency_avg  # мягко подложим Expert-у

    effective_latency = max(latency_sec, latency_avg or 0.0)

    # 2) сначала обновим мотивационный уровень/историю через _evaluate (6.1)
    base_result = self._evaluate(context, event=event, question=question, answer=answer)

    # 3) проверка сценариев 6.2 с приоритетом
    #    frustration > low_metrics > slow_response > short_replies
    try:
        order = self.scenario_order
    except AttributeError:
        order = ["frustration", "low_metrics", "slow_response", "short_replies"]

    metrics_for_rules = {
        "engagement": engagement,
        "confidence": confidence,
        "latency_sec": latency_sec,
        "latency_avg_sec": latency_avg,
        "effective_latency": effective_latency
    }

    reaction = None
    style_update = None
    triggered = []
    # Если сценарии ещё не определены (на всякий случай)
    scenarios = getattr(self, "scenarios", {})

    for name in order:
        data = scenarios.get(name)
        if not data:
            continue
        detect_fn = data.get("detect")
        if not callable(detect_fn):
            continue
        try:
            # позволим правилам использовать effective_latency
            match = detect_fn(question or "", metrics_for_rules)
        except TypeError:
            # обратная совместимость, если detect ожидал 1 аргумент
            match = detect_fn(question or "")
        except Exception:
            match = False

        # отдельный случай: slow_response — проверяем именно effective_latency
        if name == "slow_response" and not match:
            match = metrics_for_rules["effective_latency"] > getattr(self, "th_lat_slow", 45.0)

        if match:
            triggered.append(name)
            reaction = data.get("reaction")
            style_update = data.get("style")
            slot["drop_count"] = slot.get("drop_count", 0) + 1
            break  # срабатывает только один сценарий за раз

    # 4) собрать объединённый результат
    merged = dict(base_result)
    merged.update({
        "triggered": triggered,
        "reaction": reaction,
        "style_update": style_update,
        "drop_count": slot.get("drop_count", 0),
        # прозрачные метрики, чтобы видеть, почему сработал slow_response
        "metrics": {
            "engagement": engagement,
            "confidence": confidence,
            "latency_sec": latency_sec,
            "latency_avg_sec": latency_avg,
            "effective_latency": effective_latency
        }
    })

    # сохранить "last" для удобства UI/логики
    context.progress.setdefault("Motivator", {})["last"] = merged
    return merged

# Возможные состояния
STATES = [
    "start",       # начало занятия
    "goals",       # определение целей
    "task",        # выдача задания
    "support",     # поддержка/эмпатия
    "expertise",   # вопрос-ответ
    "motivation",  # мотивация
    "finish"       # завершение занятия
]

# Возможные события
EVENTS = [
    "init",            # запуск занятия
    "student_question",
    "task_completed",
    "timeout",
    "inactivity",
    "confusion",
    "end"
]

# ==========================
# 🔌 Простая интеграция FSM - Motivator
# ==========================
# Если у тебя уже есть TeachingFSM — добавим хук к мотиватору:
def attach_motivator_to_fsm(fsm: 'TeachingFSM', motivator: Motivator):
    # лёгкий «патч» метода handle_event — только для событий student_question/inactivity/end
    orig_handle = fsm.handle_event

    def _handle_event_patched(event, data=None):
        out = orig_handle(event, data)
        # после ответа эксперта (или при неактивности) — оценим мотивацию
        if event in {"student_question", "inactivity", "end"}:
            try:
                motivator.observe(event=event, context=fsm.context, question=data,
                                  answer=fsm.context.progress.get("Expert", {}).get("last_answer"))
            except Exception as e:
                print(f"[Motivator] observe error: {e}")
        return out

    fsm.handle_event = _handle_event_patched
    fsm.motivator = motivator
    print("✅ Motivator attached to FSM (events: student_question/inactivity/end)")

# --- Safety bootstrap: подхватываем/создаём контекст и модули ---

# 1) Контекст, база знаний и эксперт
if 'ctx' not in globals():
    ctx = Context(
        discipline="Цифровая культура",
        lesson_number=2,
        topic="Генерация инфографики",
        student_level=1
    )

if 'kb' not in globals():
    kb = KnowledgeBase()
    kb.load("Цифровая культура")

if 'expert' not in globals():
    expert = Expert(kb)

# 2) Опционально: FSM (если у вас он используется)
if 'fsm' not in globals():
    try:
        fsm = TeachingFSM(ctx, expert=expert)
    except Exception:
        fsm = None  # не критично для теста EventBus

# 3) Подхватываем/создаём Motivator и Organizer, если классы есть
if 'motivator' not in globals():
    motivator = None
    if 'Motivator' in globals():
        try:
            motivator = Motivator()
        except Exception:
            motivator = None  # безопасно продолжим без него

if 'organizer' not in globals():
    organizer = None
    if 'Organizer' in globals():
        try:
            organizer = Organizer()
        except Exception:
            organizer = None

# --- Сборка EventBus (важно: можно передавать None) ---
# bus = build_event_bus(
#     context=ctx,
#     expert=expert,
#     motivator=motivator,   # может быть None — это ок
#     organizer=organizer    # может быть None — это ок
# )

# # (опционально) адаптер для FSM → шина
# if fsm is not None:
#     class FSMEventAdapter:
#         def __init__(self, bus: EventBus):
#             self.bus = bus
#         def send(self, type_, payload=None, source="fsm"):
#             self.bus.publish(Event(type=type_, payload=payload or {}, source=source))
#     fsm_bus = FSMEventAdapter(bus)

# # --- Тестовый сценарий 7.1: student_question → Expert → Motivator ---
# # Старт занятия
# bus.publish(Event(type="init", payload={}, source="test"))
# # Вопрос студента
# bus.publish(Event(type="student_question", payload={"text": "Что такое инфографика?"}, source="student"))

# print("\n--- Последние события шины ---")
# for ev in bus.log[-6:]:
#     print(f"{ev.ts:.0f} | {ev.source:>10} → {ev.type:<18} | payload={list(ev.payload.keys())}")

# # Если Motivator подключён, покажем его последний снимок
# if motivator is not None:
#     last = ctx.progress.get("Motivator", {}).get("last")
#     if last:
#         print("\n[Motivator ➜ last]")
#         print(last)
#     else:
#         print("\n[Motivator] пока не дал снимок (не было expert_answer или проверок).")
# else:
#     print("\n(Motivator не подключён — передан None)")

# === SIMPLE TEST START ===
# Простой тест: инициализация, вопрос студента, завершение занятия

if __name__ == "__main__":
    print("\n=== [ТЕСТ] Запуск простой тестовой сессии ===")
    if fsm is None:
        fsm = TeachingFSM(ctx, expert=expert)

    try:
        fsm.handle_event("init")
        ctx.data = "Как ИИ влияет на копирайт?"
        fsm.handle_event("student_question")
        fsm.handle_event("end")
        print("\n✅ Все модули отработали без фатальных ошибок!")
    except Exception as e:
        print("\n❌ Произошла ошибка при тестовом прогоне:")
        print(str(e))



