# modules/motivator.py

# ============================================
# 🔥 Sprint 6.1 — Motivator (Blanchard/Hersey)
# ============================================
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

# Уровни мотивационного состояния (S1–S4)
LEVEL_NAMES = {
    1: "S1 Новичок (низкая компетентность, высокая мотивация)",
    2: "S2 Ученик в кризисе (низкая компетентность, низкая мотивация)",
    3: "S3 Продвинутый (компетентность средняя/высокая, мотивация колеблется)",
    4: "S4 Самостоятельный (высокая компетентность и мотивация)"
}

# Рекомендованные стили («ситуационное лидерство»)
LEVEL_STYLES = {
    1: {"style": "директивный + поддержка", "tone": "mentor",  "pace": "упрощённый"},
    2: {"style": "коучинг (много поддержки)", "tone": "mentor", "pace": "упрощённый"},
    3: {"style": "поддерживающий партнёр",    "tone": "partner","pace": "обычный"},
    4: {"style": "делегирование",            "tone": "partner","pace": "ускоренный"}
}

def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

@dataclass
class MotivationSnapshot:
    level: int
    name: str
    style: Dict[str, Any]
    engagement: float
    confidence: float
    latency_avg_sec: Optional[float]
    signals: Dict[str, Any]  # что сработало
    ts: float

class Motivator(TeachingFunction):
    """
    Читает сигналы из context.progress["Expert"] и ведёт motivation_level (1..4).
    Выдаёт рекомендацию по стилю общения/темпу и фиксирует «что повлияло» на переход.
    """

    def __init__(self,
                 th_conf_low=0.38, th_conf_high=0.72,
                 th_eng_low=0.40,  th_eng_high=0.68,
                 th_lat_slow=45.0, th_lat_fast=12.0,
                 hysteresis=0.06):
        # Пороги можно тонко подстраивать под дисциплину/режим
        self.th_conf_low  = th_conf_low
        self.th_conf_high = th_conf_high
        self.th_eng_low   = th_eng_low
        self.th_eng_high  = th_eng_high
        self.th_lat_slow  = th_lat_slow
        self.th_lat_fast  = th_lat_fast
        self.hysteresis   = hysteresis  # чтобы не «дёргался» уровень
        self.last_snapshot: Optional[MotivationSnapshot] = None
        
        self.scenarios = {
            "short_replies": {
                "detect": lambda q, m: q and len(q.split()) <= 3,
                "reaction": "Вижу, что ответ получился коротким. Давай разберём чуть подробнее?",
                "style": {"pace": "замедленный", "tone": "warm"}
            },
            "frustration": {
                "detect": lambda q, m: q and any(word in q.lower() for word in ["не понимаю", "сложно", "устал", "не получается"]),
                "reaction": "Это нормально чувствовать трудность. Попробуем шаг за шагом, я рядом.",
                "style": {"pace": "замедленный", "tone": "warm"}
            },
            "slow_response": {
                "detect": lambda q, m: m.get("latency_sec", 0) > 10,
                "reaction": "Не спеши, давай возьмём паузу и разберём спокойно.",
                "style": {"pace": "замедленный", "tone": "neutral"}
            },
            "low_metrics": {
                "detect": lambda q, m: m.get("engagement", 1) < 0.4 or m.get("confidence", 1) < 0.4,
                "reaction": "Кажется, стало сложнее удерживать внимание. Что тебе помогает обычно включиться?",
                "style": {"pace": "обычный", "tone": "supportive"}
            }
        }
        
        # 📌 ДОБАВИТЬ В __init__ ПОСЛЕ self.scenarios (одна строка):
        # приоритеты: frustration > low_metrics > slow_response > short_replies
        try:
            self.scenario_order = ["frustration", "low_metrics", "slow_response", "short_replies"]
        except AttributeError:
            pass

    # Инициализация хранилища в контексте
    def _ensure_slot(self, context: Context):
        context.progress.setdefault("Motivator", {})
        slot = context.progress["Motivator"]
        slot.setdefault("level", 1)                  # S1 по умолчанию
        slot.setdefault("history", [])               # история снимков
        slot.setdefault("last_check_ts", time.time())
        return slot

    def _read_expert_metrics(self, context: Context):
        ex = context.progress.get("Expert", {})
        engagement = float(ex.get("engagement", 0.5))
        confidence = float(ex.get("confidence", 0.5))
        lat_avg    = ex.get("latency_avg_sec", None)
        # Учтём статус последней задачи (если Organizer есть)
        org = context.progress.get("Organizer", {})
        last_task_status = None
        if isinstance(org.get("task_status"), dict):
            # возьмём последний по времени статус, если есть timestamp — упростим: первый попавшийся completed/needs_review
            for _tid, st in org["task_status"].items():
                if isinstance(st, dict) and st.get("status") in {"completed","needs_review"}:
                    last_task_status = st.get("status")
                    break
        return engagement, confidence, lat_avg, last_task_status

    def _decide_next_level(self, current_level: int, engagement: float, confidence: float,
                           lat_avg: Optional[float], last_task_status: Optional[str]) -> (int, Dict[str, Any]):
        sig = {"low_conf": False, "low_eng": False, "slow": False, "fast": False, "success": False}

        # Сигналы
        if confidence < (self.th_conf_low - self.hysteresis):
            sig["low_conf"] = True
        if engagement < (self.th_eng_low - self.hysteresis):
            sig["low_eng"] = True
        if lat_avg is not None and lat_avg > self.th_lat_slow:
            sig["slow"] = True
        if lat_avg is not None and lat_avg < self.th_lat_fast:
            sig["fast"] = True
        if last_task_status == "completed" or confidence > (self.th_conf_high + self.hysteresis):
            sig["success"] = True

        # Логика переходов (мягкая; максимум на 1 шаг за проверку)
        next_level = current_level

        # Понижение уровня при явном спаде
        if sig["low_conf"] or sig["low_eng"] or sig["slow"]:
            next_level = max(1, current_level - 1)

        # Повышение уровня при устойчивом успехе/быстроте
        elif sig["success"] and (engagement > self.th_eng_high or sig["fast"]):
            next_level = min(4, current_level + 1)

        # Иначе остаёмся на месте (гистерезис)
        return next_level, sig

    def process(self, context: Context) -> dict:
        """ Периодическая проверка (можно вызывать на событиях inactivity, tick, end и т.п.) """
        return self._evaluate(context, event="tick")

    def observe(self, event: str, context: Context, question: Optional[str]=None, answer: Optional[dict]=None) -> dict:
        """ Вызывать после значимых событий: student_question, student_submit, inactivity, end """
        return self._evaluate(context, event=event, question=question, answer=answer)
    
    
    def _pick_motivation(self, level: int) -> Dict[str, str]:
        """Выбираем случайную фразу и челлендж для уровня."""
        lib = MOTIVATION_LIBRARY.get(level, MOTIVATION_LIBRARY[1])
        phrase = random.choice(lib["phrases"])
        challenge = random.choice(lib["challenges"])
        return {"phrase": phrase, "challenge": challenge}
    
    #####
    def record_reflection_answer(self, context: Context, text: str):
        """Фиксирует ответ студента на рефлексивный вопрос"""
        store = context.progress.setdefault("Reflection", {})
        store.setdefault("answers", []).append({"ts": time.time(), "text": text})

        # 🔹 простая реакция-пример: если студент пишет "времени не хватает"
        if "врем" in text.lower():
            context.progress["Motivator"].setdefault("last", {}).setdefault("style", {})["pace"] = "замедленный"

        return {"status": "recorded", "answer": text}
    #####

    def _evaluate(self, context: Context, event: str, question: Optional[str]=None, answer: Optional[dict]=None) -> dict:
        slot = self._ensure_slot(context)

        # 1) Читаем последние метрики от Expert/Organizer
        engagement, confidence, lat_avg, last_task_status = self._read_expert_metrics(context)

        # 2) Решаем про уровень
        current_level = int(slot.get("level", 1))
        next_level, signals = self._decide_next_level(current_level, engagement, confidence, lat_avg, last_task_status)

        # 3) Обновляем уровень и собираем снимок
        slot["level"] = next_level
        snap = MotivationSnapshot(
            level=next_level,
            name=LEVEL_NAMES[next_level],
            style=LEVEL_STYLES[next_level],
            engagement=_clamp(engagement), confidence=_clamp(confidence),
            latency_avg_sec=lat_avg, signals=signals, ts=time.time()
        )
        self.last_snapshot = snap
        # Лёгкая история (хранить только последние 20)
        hist = slot["history"]
        hist.append({
            "ts": snap.ts,
            "event": event,
            "level": snap.level,
            "name": snap.name,
            "style": snap.style,
            "engagement": snap.engagement,
            "confidence": snap.confidence,
            "latency_avg_sec": snap.latency_avg_sec,
            "signals": snap.signals,
            "q": question,
        })
        slot["history"] = hist[-20:]
        slot["last_check_ts"] = snap.ts
        
        # 🔹 6.3: выбираем мотивационную фразу и челлендж по уровню (с рандомизацией)
        lib = MOTIVATION_LIBRARY.get(next_level, MOTIVATION_LIBRARY[1])
        mot_phrase = random.choice(lib["phrases"])
        mot_challenge = random.choice(lib["challenges"])
        motivation = {"phrase": mot_phrase, "challenge": mot_challenge}

        # 4) Результат + рекомендации по стилю/темпу/тону
        result = {
            "level": snap.level,
            "level_name": snap.name,
            "style": snap.style,               # {'style','tone','pace'}
            "metrics": {
                "engagement": snap.engagement,
                "confidence": snap.confidence,
                "latency_avg_sec": snap.latency_avg_sec
            },
            "signals": signals,
            "motivation": motivation           # 🔹 добавили
        }
        context.progress["Motivator"]["last"] = result
        
        # 5) Проверка сценариев падения мотивации (6.2)
        question_text = question or ""
        metrics_for_rules = {
            "latency_sec": (context.progress.get("Expert", {}) or {}).get("latency_sec", 0),
            "engagement": engagement,
            "confidence": confidence
        }
        reaction = None
        style_update = None
        triggered = []
        
        for name, data in self.scenarios.items():
            try:
                if data["detect"](question_text, metrics_for_rules):
                    triggered.append(name)
                    reaction = data["reaction"]
                    style_update = data["style"]
                    # ведём счётчик эпизодов
                    slot["drop_count"] = slot.get("drop_count", 0) + 1
                    break  # только один сценарий за раз
            except Exception:
                continue
        
        # включаем в результат
        result.update({
            "triggered": triggered,
            "reaction": reaction,
            "style_update": style_update,
            "drop_count": slot.get("drop_count", 0)
        })
        
         # 🔹 6.4 Мини-рефлексия
        need_reflection = False
        if slot.get("drop_count", 0) >= 3 or (signals.get("low_conf") and signals.get("low_eng")):
            need_reflection = True

        reflection_q = None
        if need_reflection:
            reflection_q = random.choice(REFLECTION_QUESTIONS)
            # сохраним в контексте историю вопросов
            context.progress.setdefault("Reflection", {})
            context.progress["Reflection"].setdefault("asked", []).append({
                "ts": snap.ts,
                "question": reflection_q,
                "triggered_by": triggered or signals
            })
            
        #####    
        # после выбора reflection_q
        asked = context.progress.setdefault("Reflection", {}).setdefault("asked", [])
        last_q = asked[-1]["question"] if asked else None
        if last_q == reflection_q:
            pool = [q for q in REFLECTION_QUESTIONS if q != last_q] or REFLECTION_QUESTIONS
            reflection_q = random.choice(pool)
        asked.append({"ts": snap.ts, "question": reflection_q, "triggered_by": triggered or signals})
        #####

        result["reflection_question"] = reflection_q
        
        return result