# core/conductor.py

# ============================================
# 🧪 Sprint 7.2 — Последовательная логика занятия (Conductor + EventBus)
# Требуется: ctx, bus, expert уже созданы (и, по возможности, organizer, motivator)
# ============================================
from typing import Optional, Dict, Any
import time

# ── 0) Фолбэк для целей (если Cartographer/goals уже есть — возьмём их)
def _get_or_make_goals(context) -> Dict[str, Any]:
    cart = context.progress.get("Cartographer", {})
    if "goals" in cart:
        return cart["goals"]
    # fallback — самые базовые цели
    topic = context.topic or "Тема занятия"
    goals = {
        "main_goal": f"Изучить тему: {topic}",
        "subgoals": [
            f"Понять ключевые понятия темы «{topic}»",
            "Выполнить одно практическое задание",
            "Оценить получившийся результат по чек‑листу"
        ],
        "level": "понимание → применение → оценка"
    }
    context.update_progress("Cartographer", {**cart, "goals": goals})
    return goals

# ── 1) Conductor — оркестратор этапов занятия
class Conductor:
    """
    Этапы: start → goals → tasks → work → reflection → wrapup → finished
    Условия переходов:
      - start: получаем init → формируем цели → goals_ready
      - goals: есть цели → создаём задания → tasks_ready
      - tasks: есть задания → переходим в work
      - work: получено >= N ответов эксперта ИЛИ зафиксирована рефлексия → reflection
      - reflection: получен ответ рефлексии → wrapup
      - wrapup: публикуем lesson_finished, считаем итоги → finished
    На каждом этапе интегрируем Organizer / Motivator, если есть.
    """

    def __init__(self, context, bus, expert=None, organizer=None, motivator=None, min_work_turns:int=2):
        self.ctx = context
        self.bus = bus
        self.expert = expert
        self.organizer = organizer
        self.motivator = motivator
        self.min_work_turns = min_work_turns

        slot = self.ctx.progress.setdefault("Conductor", {})
        slot.setdefault("stage", "start")
        slot.setdefault("work_turns", 0)
        slot.setdefault("summary", {})
        slot.setdefault("timestamps", {})
        self._mark_time("created")

        # подписки
        bus.subscribe("init", self.on_init)
        bus.subscribe("goals_ready", self.on_goals_ready)
        bus.subscribe("tasks_ready", self.on_tasks_ready)
        bus.subscribe("expert_answer", self.on_expert_answer)
        bus.subscribe("reflection_answer", self.on_reflection_answer)
        bus.subscribe("ask_reflection", self.on_ask_reflection)  # логируем факт
        # на всякий случай также слушаем student_reflection
        bus.subscribe("student_reflection", self._proxy_reflection)

    # ── вспомогательное
    def _stage(self) -> str:
        return self.ctx.progress["Conductor"]["stage"]

    def _set_stage(self, new_stage: str):
        self.ctx.progress["Conductor"]["stage"] = new_stage
        self._mark_time(f"stage:{new_stage}")
        # широковещательно сообщаем об изменении
        self.bus.publish(Event(type="stage_changed", source="conductor", payload={"stage": new_stage}))

    def _mark_time(self, key: str):
        ts = time.time()
        self.ctx.progress["Conductor"]["timestamps"][key] = ts

    def _has_tasks(self) -> bool:
        org = self.ctx.progress.get("Organizer", {})
        tasks = org.get("tasks") or org.get("Organizer", {}).get("tasks")
        return bool(tasks)

    # ── обработчики событий
    def on_init(self, ev: Event):
        if self._stage() != "start":
            return
        # формируем цели (или читаем готовые)
        goals = _get_or_make_goals(self.ctx)
        self.bus.publish(Event(type="goals_ready", source="conductor", payload={"goals": goals}))

    def on_goals_ready(self, ev: Event):
        if self._stage() not in {"start", "goals"}:
            return
        self._set_stage("goals")
        # генерируем задания (через Organizer, если есть)
        if self.organizer is not None:
            org_data = self.organizer.process(self.ctx)
            self.bus.publish(Event(type="organizer_update", source="organizer", payload={"organizer": org_data}))
        # сигнал «задания готовы»
        self.bus.publish(Event(type="tasks_ready", source="conductor", payload={"has_tasks": self._has_tasks()}))

    def on_tasks_ready(self, ev: Event):
        if self._stage() not in {"goals", "tasks"}:
            return
        # проверяем, что задания действительно существуют
        if not self._has_tasks():
            # мягко деградируем: всё равно в work, но помечаем пустой набор
            self.bus.publish(Event(type="warning", source="conductor",
                                   payload={"msg": "Organizer не предоставил задания; продолжаем в режиме work."}))
        self._set_stage("tasks")
        # переход в работу
        self._set_stage("work")

    def on_expert_answer(self, ev: Event):
        # считаем «рабочие» повороты, но только на этапе work
        if self._stage() != "work":
            return
        self.ctx.progress["Conductor"]["work_turns"] += 1
        turns = self.ctx.progress["Conductor"]["work_turns"]

        # условие перехода к рефлексии
        if turns >= self.min_work_turns:
            # попросим Motivator задать вопрос рефлексии (или сами предложим)
            self.bus.publish(Event(type="ask_reflection", source="conductor",
                                   payload={"reason": "enough_work_turns", "turns": turns}))
            self._set_stage("reflection")

    def on_ask_reflection(self, ev: Event):
        # просто логируем: вопрос рефлексии предложен (его покажет UI/Expert)
        asked = self.ctx.progress.setdefault("Reflection", {}).setdefault("asked", [])
        asked.append({"ts": time.time(), "reason": ev.payload.get("reason"), "turns": ev.payload.get("turns")})

    def _proxy_reflection(self, ev: Event):
        """Если где-то опубликовано student_reflection → нормализуем в reflection_answer"""
        text = ev.payload.get("answer") or ev.payload.get("text")
        self.bus.publish(Event(type="reflection_answer", source="conductor", payload={"text": text}))

    def on_reflection_answer(self, ev: Event):
        if self._stage() != "reflection":
            # можно позволить рефлексию и вне этапа, но для канонического цикла — выходим
            return
        # сохраняем ответ и переходим к итогам
        reflect = self.ctx.progress.setdefault("Reflection", {})
        reflect.setdefault("answers", []).append({"ts": time.time(), "text": ev.payload.get("text", "")})
        self._set_stage("wrapup")
        self._finish()

    # ── подведение итогов
    def _finish(self):
        # собираем лёгкий итог
        expert_hist = self.ctx.progress.get("Expert", {}).get("dialog_history", [])
        organizer = self.ctx.progress.get("Organizer", {})
        motivator = self.ctx.progress.get("Motivator", {}).get("last", {})

        summary = {
            "topic": self.ctx.topic,
            "answers_count": len(expert_hist),
            "work_turns": self.ctx.progress["Conductor"]["work_turns"],
            "tasks_available": bool(organizer.get("tasks")),
            "motivation_level": self.ctx.progress.get("Motivator", {}).get("level", None),
            "style": motivator.get("style"),
        }
        self.ctx.progress["Conductor"]["summary"] = summary

        # публикуем итоги и закрываем занятие
        self.bus.publish(Event(type="lesson_finished", source="conductor", payload={"summary": summary}))
        self._set_stage("finished")

# ── 2) Подключаем Conductor к уже существующему bus
conductor = Conductor(
    context=ctx,
    bus=bus,
    expert=expert,
    organizer=Organizer() if 'Organizer' in globals() else None,
    motivator=motivator if 'motivator' in globals() else None,
    min_work_turns=2  # можно увеличить до 3–4 для реальной пары
)

#####
# подписываемся на события перезапуска (после build_event_bus и создания Conductor)
#bus.subscribe("restart", make_restart_handler(conductor, bus))
#####

# Доп. лог — удобно видеть смену этапов и итог
def _stage_logger(ev: Event):
    if ev.type in {"stage_changed", "lesson_finished"}:
        print(f"🎚  {ev.type} →", ev.payload)

bus.subscribe("stage_changed", _stage_logger)
bus.subscribe("lesson_finished", _stage_logger)

print("✅ Conductor подключён. Текущая стадия:", ctx.progress["Conductor"]["stage"])