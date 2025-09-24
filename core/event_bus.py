# core/event_bus.py

# ============================================
# 🧪 Sprint 7.1 — EventBus / Dispatcher + тест
# ============================================
from dataclasses import dataclass
from typing import Callable, Dict, List, Any, Optional
import time
import uuid

# ---------- 1) Структура события ----------

@dataclass
class Event:
    type: str                    # тип: 'student_question', 'expert_answer', ...
    payload: Dict[str, Any]      # полезная нагрузка (данные)
    source: str = "system"       # откуда пришло (student, expert, motivator, fsm, system)
    ts: float = None             # timestamp

    def __post_init__(self):
        if self.ts is None:
            self.ts = time.time()
    def __repr__(self):
        return f"Event(type={self.type!r}, source={self.source!r}, ts={int(self.ts)}, payload_keys={list(self.payload.keys())})"

# ---------- 2) Шина событий ----------

class EventBus:
    def __init__(self, context: Context):
        self.context = context
        self._subs: Dict[str, List[Callable[[Event], None]]] = {}
        # простой лог в контексте
        context.progress.setdefault("EventBus", {})
        context.progress["EventBus"].setdefault("log", [])
        context.progress["EventBus"].setdefault("id", str(uuid.uuid4()))

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Подписка обработчика на тип события."""
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event: Event):
        """Публикация события всем подписчикам + логирование."""
        # лог
        self._log(event)
        # диспетчеризация
        for handler in self._subs.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                self._log(Event(
                    type="error",
                    source="eventbus",
                    payload={"reason": str(e), "during": event.type}
                ))

    def _log(self, event: Event):
        rec = {
            "ts": event.ts,
            "type": event.type,
            "source": event.source,
            "payload_keys": list(event.payload.keys())
        }
        log = self.context.progress["EventBus"]["log"]
        log.append(rec)
        self.context.progress["EventBus"]["log"] = log[-200:]  # обрезаем длинный лог

# ---------- 3) Адаптеры под наши модули ----------

def make_student_question_handler(expert: 'Expert', bus: EventBus):
    """student_question → Expert.respond → publish(expert_answer)"""
    def _handler(ev: Event):
        q_text = ev.payload.get("text", "").strip()
        if not q_text:
            return
        # ответ эксперта
        answer = expert.respond(q_text, bus.context)
        # публикуем событие ответа эксперта
        bus.publish(Event(
            type="expert_answer",
            source="expert",
            payload={"question": q_text, "answer": answer}
        ))
    return _handler

def make_expert_answer_handler_motivation(motivator: Optional['Motivator'], bus: EventBus):
    """expert_answer → Motivator.observe (если есть) → publish(motivation_update)"""
    def _handler(ev: Event):
        if motivator is None:
            return
        ans = ev.payload.get("answer", {})
        q   = ev.payload.get("question", "")
        # пусть Motivator использует событие как "student_question"
        mot = motivator.observe(event="student_question", context=bus.context,
                                question=q, answer=ans)
        # публикуем событие с обновлением мотивации/стиля
        bus.publish(Event(
            type="motivation_update",
            source="motivator",
            payload={"last": mot}
        ))
    return _handler

def make_expert_answer_handler_organizer(organizer: Optional['Organizer'], bus: EventBus):
    """(опционально) expert_answer → Organizer.process → publish(organizer_update)"""
    def _handler(ev: Event):
        if organizer is None:
            return
        # при каждом содержательном ответе можем убедиться, что задания сгенерированы
        org_data = organizer.process(bus.context)
        bus.publish(Event(
            type="organizer_update",
            source="organizer",
            payload={"organizer": org_data}
        ))
    return _handler

# ---------- 4) Вспомогательный адаптер FSM → Bus (необязательно) ----------
def attach_fsm_bus_adapter(fsm: 'TeachingFSM', bus: EventBus):
    """
    Добавляет в FSM метод route_via_bus(event, data=None),
    чтобы можно было направлять события в шину.
    """
    def _route(event_type: str, data: Any = None, source: str = "fsm"):
        payload: Dict[str, Any] = {}
        if isinstance(data, str):
            payload["text"] = data
        elif isinstance(data, dict):
            payload.update(data)
        bus.publish(Event(type=event_type, source=source, payload=payload))
    fsm.route_via_bus = _route  # monkey-patch
    return fsm

# ---------- 5) Сборка bus + подписки ----------
def build_event_bus(context: Context,
                    expert: Optional['Expert']=None,
                    motivator: Optional['Motivator']=None,
                    organizer: Optional['Organizer']=None) -> EventBus:
    bus = EventBus(context)
    # маршруты:
    if expert:
        bus.subscribe("student_question", make_student_question_handler(expert, bus))
    if motivator:
        bus.subscribe("expert_answer", make_expert_answer_handler_motivation(motivator, bus))
    if organizer:
        bus.subscribe("expert_answer", make_expert_answer_handler_organizer(organizer, bus))
    # можно логировать всё базово
    def _logger(ev: Event):
        print(f"🪵 [LOG] {ev.type} <- {ev.source} :: keys={list(ev.payload.keys())}")
    # подпишем логер на основные события
    for et in ["student_question", "expert_answer", "motivation_update", "organizer_update", "error"]:
        bus.subscribe(et, _logger)
    return bus

# ---------- 6) Мини‑проверка (самодостаточный сценарий) ----------
# Предполагается, что у вас уже созданы kb / expert / motivator / organizer / ctx / fsm ранее.
# Если нет — раскомментируйте следующие строки-рычаги для простого стенда:
"""
kb = KnowledgeBase(); kb.load("Цифровая культура")
expert = Expert(kb)
motivator = Motivator()
organizer = Organizer()
ctx = Context(discipline="Цифровая культура", lesson_number=2, topic="Генерация инфографики", student_level=1)
fsm = TeachingFSM(ctx, expert=expert)  # если FSM уже есть
"""

# 6.1 — Собираем шину
bus = build_event_bus(context=ctx, expert=expert, motivator=motivator, organizer=Organizer() if 'Organizer' in globals() else None)

# добавь TTS:
tts = attach_tts_to_bus(bus, engine="piper")   # или "rhvoice"

# (опционально) подключаем адаптер к FSM, чтобы можно было посылать в шину
if 'fsm' in globals():
    attach_fsm_bus_adapter(fsm, bus)