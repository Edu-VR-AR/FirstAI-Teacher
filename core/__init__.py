# core/__init__.py

import os
import glob

from typing import List
from pathlib import Path

from datetime import datetime

import re

def extract_knowledge_types(docs: list) -> dict:
    facts = []
    procedures = []
    meta = []

    for doc in docs:
        sentences = re.split(r'[.!?]', doc)  # простая сегментация на предложения
        for sent in sentences:
            s = sent.lower().strip()
            if any(trigger in s for trigger in FACT_TRIGGERS):
                facts.append(sent.strip())
            elif any(trigger in s for trigger in PROCEDURE_TRIGGERS):
                procedures.append(sent.strip())
            elif any(trigger in s for trigger in META_TRIGGERS):
                meta.append(sent.strip())

    return {
        "facts": facts[:5],        # ограничим по 5 примеров
        "procedures": procedures[:5],
        "meta": meta[:5]
    }

def start_task(context: Context, task_id: str):
    for task in context.progress.get("Organizer", {}).get("tasks", []):
        if task["id"] == task_id:
            task["start_time"] = datetime.now().isoformat()
            task["is_completed"] = False
            print(f"▶️ Задание {task_id} начато.")
            return

def mark_task_complete(context: Context, task_id: str):
    for task in context.progress.get("Organizer", {}).get("tasks", []):
        if task["id"] == task_id:
            end_time = datetime.now()
            task["end_time"] = end_time.isoformat()
            if task["start_time"]:
                start_time = datetime.fromisoformat(task["start_time"])
                task["duration_sec"] = (end_time - start_time).total_seconds()
            else:
                task["duration_sec"] = None
            task["is_completed"] = True
            print(f"✅ Задание {task_id} завершено.")
            return

def update_task_status(context: Context, task_id: str, status: str, answer: str = None):
    if status not in ["not_started", "in_progress", "completed", "needs_review"]:
        print(f"⚠️ Недопустимый статус: {status}")
        return

    for task in context.progress.get("Organizer", {}).get("tasks", []):
        if task["id"] == task_id:
            task["status"] = status
            if answer:
                task["student_answer"] = answer
            print(f"📌 Обновлён статус задания {task_id} → {status}")
            return

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from nltk.corpus import stopwords
import nltk

# Загружаем стоп-слова один раз
nltk.download('stopwords')

# Формируем список русских стоп-слов
russian_stopwords = stopwords.words("russian")
russian_stopwords.extend(['это', 'нею'])  # твои дополнительные слова

class KnowledgeBase:
    def __init__(self):
        self.docs = []
        self.doc_names = []
        self.vectorizer = None
        self.doc_vectors = None

    def load(self, discipline: str):
        self.docs = load_documents(discipline)
        self.doc_names = [f"doc_{i+1}" for i in range(len(self.docs))]
        if not self.docs:
            print("⚠️ База знаний пуста")
            return
        

        
        self.vectorizer = TfidfVectorizer(stop_words=russian_stopwords)
        self.doc_vectors = self.vectorizer.fit_transform(self.docs)
        print(f"✅ Индексировано {len(self.docs)} документов по дисциплине '{discipline}'.")

    def search(self, query: str, top_k: int = 2):
        if not self.doc_vectors is None:
            query_vec = self.vectorizer.transform([query])
            scores = np.dot(query_vec, self.doc_vectors.T).toarray()[0]
            top_indices = np.argsort(scores)[::-1][:top_k]
            return [(self.docs[i], self.doc_names[i], scores[i]) for i in top_indices]
        else:
            return []

# --- intents: детектор типов вопросов
import re
from typing import List, Dict

INTENT_PATTERNS: Dict[str, List[str]] = {
    "why": [r"\bпочему\b", r"\bзачем\b", r"\bпо какой причине\b"],
    "how": [r"\bкак\b", r"\bкаким образом\b", r"\bпорядок\b", r"\bшаг(и|ов)\b"],
    "what_if": [r"\bчто если\b", r"\bа если\b"],
    "examples": [r"\bпример(ы)?\b", r"\bкейсы?\b", r"\bиллюстраци(я|и)\b"]
}

def detect_intents(question: str) -> List[str]:
    q = question.lower()
    hits = [intent for intent, pats in INTENT_PATTERNS.items() if any(re.search(p, q) for p in pats)]
    if not hits:
        if q.startswith("что такое"):
            hits = ["examples"]
        else:
            hits = ["how"]
    return hits

# --- форматирование ответа по типам
def _format_by_intents(answer_base: str, intents: List[str]) -> str:
    sections = []
    for it in intents:
        if it == "why":
            sections.append(
                "Почему это важно:\n"
                "- Связь с целями занятия\n"
                "- Какие ошибки предотвращает\n"
                "- Как влияет на результат"
            )
        elif it == "how":
            sections.append(
                "Как действовать (шаги):\n"
                "1) Изучите требования\n"
                "2) Подготовьте данные/макет\n"
                "3) Примените правила из материалов\n"
                "4) Проверьте критерии качества"
            )
        elif it == "what_if":
            sections.append(
                "Что если (разбор вариантов):\n"
                "- Если данных мало → используйте минималистичную схему\n"
                "- Если аудитория не экспертная → упрощайте подписи\n"
                "- Если форм‑фактор узкий → избегайте перегруза"
            )
        elif it == "examples":
            sections.append(
                "Примеры/кейсы:\n"
                "- Одностраничная инфографика для отчёта\n"
                "- Сравнительная диаграмма для презентации\n"
                "- Пояснительная визуализация для учебного плаката"
            )
    return f"{answer_base}\n\n" + ("\n\n".join(sections) if sections else "")

# --- детектор уровня детализации в вопросе
import re

def detect_detail_level(question: str) -> str:
    q = question.lower()
    if re.search(r"\b(кратко|коротко|в двух словах)\b", q):
        return "short"
    if re.search(r"\b(подробно|развернуто|детально)\b", q):
        return "long"
    return "short"  # дефолт

# --- «краткая выжимка» из базового ответа
def make_brief(text: str, limit: int = 300) -> str:
    t = text.strip().replace("\n\n", "\n")
    return (t[:limit] + "…") if len(t) > limit else t

# --- формируем explanation-секции по intents (используем уже имеющийся _format_by_intents)
def make_explanation(answer_base: str, intents: list, detail: str) -> str:
    # берём наш предыдущий форматтер из 4.2
    expl = _format_by_intents("", intents).strip()
    if detail == "long":
        # для «long» добавим базовый фрагмент как lead-in
        return f"{answer_base}\n\n{expl}" if expl else answer_base
    else:
        # для «short» только структурные подсказки по намерениям
        return expl or "Ключевая мысль: см. основную часть ответа."

# --- рекомендации следующих шагов
def build_next_steps(intents: list, context: Context) -> list:
    steps = []
    # подсказка перейти к действию, если есть Organizer.tasks
    org = context.progress.get("Organizer", {})
    tasks = org.get("tasks", [])
    action_tasks = [t for t in tasks if t.get("type") in ("action", "text", "reflection")]
    if action_tasks:
        steps.append(f"Выполни задание: «{action_tasks[0]['instruction']}»")
    # общие ветвления по намерениям
    if "how" in intents:
        steps.append("Сверься с чек-листом качества из материалов занятия.")
    if "why" in intents:
        steps.append("Выдели 2–3 аргумента, почему это важно именно для твоей аудитории.")
    if "examples" in intents:
        steps.append("Найди 2 примера из реальных источников и кратко сравни их.")
    if "what_if" in intents:
        steps.append("Опиши 1–2 альтернативы для твоего кейса и выбери подходящую.")
    # запасной нейтральный шаг
    if not steps:
        steps.append("Задай уточняющий вопрос или перейди к выполнению ближайшего задания.")
    return steps

# =========================
# 🧩 Sprint 5.2 — Signals
# =========================
from datetime import datetime, timedelta

# 1) Объективные сигналы из Organizer + признаки фрустрации
def detect_objective_situation(context: Context) -> str:
    org = context.progress.get("Organizer", {})
    status_map = org.get("task_status", {})  # ожидается {task_id: {"status": "...", "is_completed": bool, ...}}

    # 1) успех: есть завершённые задачи
    has_completed = any(v.get("status") in {"completed"} or v.get("is_completed") for v in status_map.values())
    if has_completed:
        return "success"

    # 2) ошибка/нужен разбор: есть задачи с needs_review/error
    has_issue = any(v.get("status") in {"needs_review", "error"} for v in status_map.values())
    if has_issue:
        return "error"

    # 3) фрустрация: частые короткие уточнения или (опционально) долгая пауза
    hist = context.progress.get("Expert", {}).get("dialog_history", [])
    if len(hist) >= 3:
        last3 = [h.get("question", "").lower() for h in hist[-3:]]
        short_count = sum(len(q.split()) <= 4 for q in last3)
        if short_count >= 2:  # два коротких уточнения из последних трёх
            return "frustration"

    # (опционально) долгая пауза: если у тебя где-то хранится timestamp последней активности — можно учесть
    # last_time = context.progress.get("last_activity_ts")
    # if last_time and (datetime.utcnow() - last_time) > timedelta(minutes=15):
    #     return "frustration"

    return "start"

# 2) Смешивание: приоритет объективных сигналов над текстовыми (из 5.1 — detect_situation)
def detect_situation_mixed(user_text: str, context: Context) -> str:
    state_signal = detect_objective_situation(context)
    if state_signal != "start":
        return state_signal
    # если объективных нет — используем текстовый детектор (из 5.1)
    return detect_situation(user_text)

# 3) Патч RelationalTuner.embellish: используем смешанный детектор
#    (класс RelationalTuner уже объявлен ранее — переопределим только метод)
def _rt_embellish_patched(self,
                          answer_data: dict,
                          context: Context,
                          user_text: str = None,
                          tone_override: str = None,
                          position: str = None) -> dict:
    tone = tone_override or self.default_tone
    pos = position or self.position

    # ключевая замена:
    situation = detect_situation_mixed(user_text or answer_data.get("question", ""), context)

    chosen = pick_empathy_line(context, situation, tone)
    intro, outro = None, None

    if pos == "auto":
        if situation in {"error", "doubt", "frustration", "help_request"}:
            intro = chosen["phrase"]
        elif situation in {"success", "end"}:
            outro = chosen["phrase"]
        else:
            intro = chosen["phrase"]
    elif pos == "intro":
        intro = chosen["phrase"]
    elif pos == "outro":
        outro = chosen["phrase"]
    elif pos == "both":
        intro = chosen["phrase"]
        outro = pick_empathy_line(context, situation, tone)["phrase"]

    # собираем финальный текст
    full_text = ""
    if intro:
        full_text += intro + "\n\n"
    full_text += answer_data.get("answer", "")
    if outro:
        full_text += "\n\n" + outro

    # метаданные для UI/логики
    answer_data["empathy"] = {
        "situation": chosen["situation"],
        "tone": chosen["tone"],
        "intro": intro,
        "outro": outro
    }
    answer_data["answer_empathic"] = full_text
    return answer_data

# применяем патч
RelationalTuner.embellish = _rt_embellish_patched

print("✅ Sprint 5.2: objective signals integrated into RelationalTuner.embellish")

# ================================
# 🧩 Patch: Empathy inside Expert
# ================================
import random

# 0) Страховка: если тюнер ещё не создан — создадим
try:
    tuner
except NameError:
    try:
        tuner = RelationalTuner(default_tone="warm", position="auto")
    except NameError:
        # если класс ещё не импортирован — минимальная заглушка,
        # но в твоём проекте RelationalTuner уже есть из 5.1
        class _DummyTuner:
            def embellish(self, answer_data, context, user_text=None, tone_override=None, position=None):
                # без тюнера просто возвращаем как есть
                answer_data["answer_empathic"] = answer_data.get("answer", "")
                answer_data["empathy"] = {
                    "situation": "start", "tone": "warm", "intro": None, "outro": None
                }
                return answer_data
        tuner = _DummyTuner()

# 1) Страховка: смешанный детектор ситуаций (из 5.2). Если нет — fallback на текстовый.
def _detect_situation_for_empathy(user_text: str, context: 'Context') -> str:
    try:
        return detect_situation_mixed(user_text, context)  # приоритет объективных сигналов
    except NameError:
        try:
            return detect_situation(user_text)  # текстовый детектор из 5.1
        except NameError:
            return "start"

# 2) Патчим только «хвост» Expert.respond: после сборки answer_data → добавляем эмпатию
_old_respond = Expert.respond

def _respond_with_empathy(self, question: str, context: 'Context') -> dict:
    # вызываем оригинальную реализацию (с RAG, памятью, тоном/уровнем и метриками 5.4)
    answer_data = _old_respond(self, question, context)

    # если это сброс памяти — пропускаем украшение
    if isinstance(answer_data, dict) and answer_data.get("status") == "dialog_cleared":
        return answer_data

    # эмпатическая обвязка
    # (позиция тюнера уже настроена, но можно переопределить тут: position="intro"/"outro"/"both")
    try:
        enriched = tuner.embellish(
            answer_data,
            context,
            user_text=question,                 # важно: детекция ситуации берёт именно реплику студента
            tone_override=None,                 # можно подменить на context.tone при желании
            position=None                       # None → использовать политику тюнера ("auto")
        )
    except Exception:
        # на всякий случай не ломаем ответ
        enriched = answer_data
        enriched.setdefault("answer_empathic", enriched.get("answer", ""))
        enriched.setdefault("empathy", {"situation": _detect_situation_for_empathy(question, context),
                                        "tone": "warm", "intro": None, "outro": None})

    # обновим last_answer в истории (чтобы UI видел обогащённый ответ)
    try:
        context.progress["Expert"]["last_answer"] = enriched
        # сохраним ещё и «последнюю эмпатию» в тюнере (удобно для отладки/UI)
        context.progress.setdefault("RelationalTuner", {})
        context.progress["RelationalTuner"]["last"] = enriched.get("empathy")
    except Exception:
        pass

    return enriched

# применяем патч
Expert.respond = _respond_with_empathy

print("✅ Empathy integrated: Expert.respond теперь возвращает answer_empathic + empathy")

# ==========================================
# ⏱ Patch: latency/tempo for Expert (Sprint 5.4+)
# ==========================================
import time
from collections import deque

# параметры — можно подправить под себя
LAT_FAST_SEC   = 12.0   # быстрее этого — считаем "высокая вовлечённость"
LAT_SLOW_SEC   = 45.0   # медленнее этого — "низкая вовлечённость"
LAT_WINDOW_N   = 8      # скользящее окно средних
DELTA_ENG_FAST = +0.06  # насколько менять engagement за быстрый ответ
DELTA_ENG_SLOW = -0.06  # насколько менять engagement за медленный ответ
DELTA_CONF_UP  = +0.05  # поправка уверенности за короткие уверенные фразы
DELTA_CONF_DN  = -0.07  # поправка уверенности за сомнение/долгую паузу

# страхуем: инициализация буфера латентностей один раз в контексте
def _ensure_latency_buffer(context: 'Context'):
    context.progress.setdefault("Expert", {})
    if "latency_buffer" not in context.progress["Expert"]:
        context.progress["Expert"]["latency_buffer"] = deque(maxlen=LAT_WINDOW_N)

# патчим Expert.respond — перехватываем «хвост»
_old_expert_respond_latency = Expert.respond

def _respond_with_latency(self, question: str, context: 'Context') -> dict:
    # 1) до вызова оригинала — измеряем задержку
    now = time.time()
    # гарантируем поля
    context.progress.setdefault("Expert", {})
    last_ts = context.progress["Expert"].get("last_interaction_time", None)
    latency = None
    if last_ts is not None:
        latency = max(0.0, now - last_ts)
    # обновим last_interaction_time сразу — чтобы параллельные обработчики не сбивали
    context.progress["Expert"]["last_interaction_time"] = now

    # 2) вызываем «старый» respond (внутри он уже обновит engagement/confidence по своим правилам)
    answer = _old_expert_respond_latency(self, question, context)

    # 3) если это сброс памяти — выходим как есть
    if isinstance(answer, dict) and answer.get("status") == "dialog_cleared":
        return answer

    # 4) донастройка метрик с учётом latency (мягкое влияние + окно)
    _ensure_latency_buffer(context)
    buf: deque = context.progress["Expert"]["latency_buffer"]
    if latency is not None:
        buf.append(latency)

        # базовая поправка вовлечённости
        eng = context.progress["Expert"].get("engagement", 0.5)
        if latency <= LAT_FAST_SEC:
            eng += DELTA_ENG_FAST
        elif latency >= LAT_SLOW_SEC:
            eng += DELTA_ENG_SLOW
        # клиппинг
        eng = min(max(eng, 0.0), 1.0)
        context.progress["Expert"]["engagement"] = eng

        # лёгкая коррекция уверенности: очень длинные паузы слегка «роняют» уверенность
        conf = context.progress["Expert"].get("confidence", 0.5)
        if latency >= LAT_SLOW_SEC * 1.5:
            conf += DELTA_CONF_DN/2
        elif latency <= LAT_FAST_SEC/2:
            conf += DELTA_CONF_UP/2
        conf = min(max(conf, 0.0), 1.0)
        context.progress["Expert"]["confidence"] = conf

    # 5) добавляем служебные поля в ответ
    avg = (sum(context.progress["Expert"]["latency_buffer"]) / len(context.progress["Expert"]["latency_buffer"])
           if context.progress["Expert"]["latency_buffer"] else None)
    answer["latency_sec"] = latency
    answer["latency_avg_sec"] = avg

    # 6) при желании можно автоподстройку темпа сделать чуть агрессивнее/мягче на основе avg
    # (пример без резких скачков — только комментарий, если захочешь активировать, раскомментируй)
    # if avg is not None:
    #     if avg > LAT_SLOW_SEC and answer.get("pace") != "упрощённый":
    #         answer["pace"] = "упрощённый"
    #     elif avg < LAT_FAST_SEC and answer.get("pace") != "ускоренный":
    #         answer["pace"] = "ускоренный"

    return answer

# применяем патч
Expert.respond = _respond_with_latency

print("✅ Latency tracking integrated: ответ теперь включает latency_sec и latency_avg_sec; метрики скорректированы.")

# ===============================
# ⏱ Fix patch: latency ordering
# + gentle pace auto-adjust
# ===============================
import time
from collections import deque

LAT_FAST_SEC   = 12.0
LAT_SLOW_SEC   = 45.0
LAT_WINDOW_N   = 8
DELTA_ENG_FAST = +0.06
DELTA_ENG_SLOW = -0.06
DELTA_CONF_UP  = +0.05
DELTA_CONF_DN  = -0.07

def _ensure_latency_buffer(context: 'Context'):
    context.progress.setdefault("Expert", {})
    if "latency_buffer" not in context.progress["Expert"]:
        context.progress["Expert"]["latency_buffer"] = deque(maxlen=LAT_WINDOW_N)

# сохранём ссылку на текущий Expert.respond (с эмпатией и т.п.)
_old_expert_respond_latency = Expert.respond

def _respond_with_latency_fixed(self, question: str, context: 'Context') -> dict:
    # 1) измеряем реальную задержку БЕЗ изменения last_interaction_time
    now = time.time()
    context.progress.setdefault("Expert", {})
    last_ts = context.progress["Expert"].get("last_interaction_time", None)
    latency = None
    if last_ts is not None:
        latency = max(0.0, now - last_ts)

    # 2) вызываем оригинальный respond (пусть он использует last_ts как есть)
    answer = _old_expert_respond_latency(self, question, context)

    # 3) если это сброс — возвращаем как есть и обновляем last_interaction_time на now
    context.progress["Expert"]["last_interaction_time"] = now
    if isinstance(answer, dict) and answer.get("status") == "dialog_cleared":
        return answer

    # 4) обновляем метрики с учётом latency
    _ensure_latency_buffer(context)
    buf: deque = context.progress["Expert"]["latency_buffer"]
    if latency is not None:
        buf.append(latency)

        eng = context.progress["Expert"].get("engagement", 0.5)
        if latency <= LAT_FAST_SEC:
            eng += DELTA_ENG_FAST
        elif latency >= LAT_SLOW_SEC:
            eng += DELTA_ENG_SLOW
        context.progress["Expert"]["engagement"] = min(max(eng, 0.0), 1.0)

        conf = context.progress["Expert"].get("confidence", 0.5)
        if latency >= LAT_SLOW_SEC * 1.5:
            conf += DELTA_CONF_DN/2
        elif latency <= LAT_FAST_SEC/2:
            conf += DELTA_CONF_UP/2
        context.progress["Expert"]["confidence"] = min(max(conf, 0.0), 1.0)

    # 5) добавим служебные поля + мягкую автоподстройку темпа по средней латентности
    avg = (sum(buf) / len(buf)) if buf else None
    answer["latency_sec"] = latency
    answer["latency_avg_sec"] = avg

    if avg is not None:
        # аккуратно, без «дёрганья»: меняем только если явно вышли за пороги
        if avg > LAT_SLOW_SEC and answer.get("pace") != "упрощённый":
            answer["pace"] = "упрощённый"
        elif avg < LAT_FAST_SEC and answer.get("pace") != "ускоренный":
            answer["pace"] = "ускоренный"
        else:
            # оставляем как есть (обычный)
            pass

    return answer

# применяем фикс
Expert.respond = _respond_with_latency_fixed

print("✅ Latency fix applied: last_interaction_time обновляется после исходного respond; темп подстраивается по средней латентности.")

# =========================================
# ✅ Unified Expert.respond (no wrappers)
# RAG + memory + levels/tones + empathy + latency
# =========================================
import time, random
from collections import deque

# --- Параметры латентности (можно подправить под режим live/async)
LAT_FAST_SEC   = 12.0
LAT_SLOW_SEC   = 45.0
LAT_WINDOW_N   = 8
DELTA_ENG_FAST = +0.06
DELTA_ENG_SLOW = -0.06
DELTA_CONF_UP  = +0.05
DELTA_CONF_DN  = -0.07

# Страховка: тюнер эмпатии
try:
    tuner
except NameError:
    try:
        tuner = RelationalTuner(default_tone="warm", position="auto")
    except NameError:
        class _DummyTuner:
            def embellish(self, answer_data, context, user_text=None, tone_override=None, position=None):
                answer_data["answer_empathic"] = answer_data.get("answer", "")
                answer_data["empathy"] = {"situation":"start","tone":"warm","intro":None,"outro":None}
                return answer_data
        tuner = _DummyTuner()

def _ensure_latency_struct(context: 'Context'):
    context.progress.setdefault("Expert", {})
    ex = context.progress["Expert"]
    ex.setdefault("dialog_history", [])
    ex.setdefault("last_answer", None)
    ex.setdefault("engagement", 0.5)
    ex.setdefault("confidence", 0.5)
    ex.setdefault("last_interaction_time", time.time())
    if "latency_buffer" not in ex:
        ex["latency_buffer"] = deque(maxlen=LAT_WINDOW_N)

# === Полная замена метода respond ===
def _expert_respond_unified(self, question: str, context: 'Context') -> dict:
    print(f"[Expert] Вопрос: {question}")
    _ensure_latency_struct(context)

    # Сброс памяти
    if question.strip().lower() in {"сброс", "reset", "очистить память"}:
        return reset_dialog(context)

    ex = context.progress["Expert"]

    # 1) Latency: измеряем по прошлому таймстемпу (не меняем его до конца обработки)
    now = time.time()
    last_ts = ex.get("last_interaction_time", now)
    latency = max(0.0, now - last_ts) if last_ts else None

    # 2) Обновляем «семантические» метрики (вовлечённость/уверенность) по тексту
    #    (твои функции/логика 5.4)
    # Простейшая версия: быстрый ответ ↑ вовлечённость, ключевые слова сдвигают уверенность
    ql = question.lower()
    if latency is not None:
        if latency <= LAT_FAST_SEC:
            ex["engagement"] = min(1.0, ex.get("engagement",0.5) + DELTA_ENG_FAST)
        elif latency >= LAT_SLOW_SEC:
            ex["engagement"] = max(0.0, ex.get("engagement",0.5) + DELTA_ENG_SLOW)
    if any(w in ql for w in ["не понимаю","сложно","устал","плохо"]):
        ex["confidence"] = max(0.0, ex.get("confidence",0.5) + DELTA_CONF_DN)
    if any(w in ql for w in ["получилось","спасибо","понятно","легко"]):
        ex["confidence"] = min(1.0, ex.get("confidence",0.5) + DELTA_CONF_UP)

    # 3) Намерения и детализация
    intents = detect_intents(question)           # ['why','how','what_if','examples']
    detail  = detect_detail_level(question)      # 'short'|'long' (или твои варианты)

    # 4) Поддержка follow-up
    history = ex["dialog_history"]
    augmented_query, in_reply_to = question, None
    def _is_followup(q: str) -> bool:
        q = q.strip().lower()
        if len(q.split()) <= 4: return True
        if re.match(r"^(а|и)\b", q): return True
        if re.search(r"\b(подробнее|поясни|уточни|разверни)\b", q): return True
        return False
    if history and _is_followup(question):
        last = history[-1]
        in_reply_to = last.get("question")
        prev_snippet = (last.get("answer") or "")[:200]
        augmented_query = f"{in_reply_to}. {question}. Контекст: {prev_snippet}"

    # 5) RAG-поиск
    results = self.kb.search(augmented_query, top_k=2)
    if not results:
        base = "Извините, в базе знаний нет информации по этому вопросу."
        sources = []
    else:
        combined_text = "\n".join([doc for doc, _, _ in results])
        base = f"На основе материалов курса:\n{combined_text[:800]}..."
        sources = [name for _, name, _ in results]

    # 6) Формируем ответ/пояснение/next_steps
    answer = make_brief(base, 300) if detail == "short" else base
    explanation = make_explanation(base, intents, detail)
    next_steps  = build_next_steps(intents, context)

    # 7) Подача (темп/манера) по уверенности (мягко)
    conf = ex["confidence"]
    if conf < 0.3:
        pace = "упрощённый"; tone = "дружелюбный наставник"
    elif conf > 0.7:
        pace = "ускоренный";  tone = "партнёр по проекту"
    else:
        pace = "обычный";     tone = "нейтральный преподаватель"

    answer_data = {
        "question": question,
        "in_reply_to": in_reply_to,
        "intents": intents,
        "detail": detail,
        "answer": answer,
        "explanation": explanation,
        "sources": sources,
        "next_steps": next_steps,
        "pace": pace,
        "tone": tone,
        "engagement": ex["engagement"],
        "confidence": ex["confidence"]
    }

    # 8) Эмпатическая обвязка
    try:
        enriched = tuner.embellish(
            answer_data,
            context,
            user_text=question,
            tone_override=None,
            position=None  # auto
        )
    except Exception:
        enriched = answer_data
        enriched.setdefault("answer_empathic", enriched.get("answer",""))
        enriched.setdefault("empathy", {"situation":"start","tone":"warm","intro":None,"outro":None})

    # 9) Latency buffer + средняя + мягкая автоподстройка темпа по среднему
    _ensure_latency_struct(context)
    buf: deque = ex["latency_buffer"]
    if latency is not None:
        buf.append(latency)
    avg = (sum(buf)/len(buf)) if buf else None
    enriched["latency_sec"] = latency
    enriched["latency_avg_sec"] = avg
    if avg is not None:
        if   avg > LAT_SLOW_SEC and enriched.get("pace") != "упрощённый":
            enriched["pace"] = "упрощённый"
        elif avg < LAT_FAST_SEC and enriched.get("pace") != "ускоренный":
            enriched["pace"] = "ускоренный"

    # 10) Обновляем last_interaction_time только в самом конце
    ex["last_interaction_time"] = now

    # 11) Сохраняем историю
    history.append(enriched)
    ex["last_answer"] = enriched
    context.progress.setdefault("RelationalTuner", {})
    context.progress["RelationalTuner"]["last"] = enriched.get("empathy")

    return enriched

# Подменяем метод класса на консолидированный
Expert.respond = _expert_respond_unified

print("✅ Expert.respond заменён на единый вариант (без обёрток): RAG + память + уровни/тон + эмпатия + latency.")

import random

MOTIVATION_LIBRARY = {
    1: {
        "phrases": [
            "Отличное начало — шаг за шагом!",
            "Ты на верном пути, не переживай, что пока сложно.",
            "Важно, что ты пробуешь. Результат придёт.",
            "Сделаем это вместе, не спеша.",
            "Помни: каждая мелочь — это часть большого успеха!"
        ],
        "challenges": [
            "Попробуй сформулировать мысль одним предложением.",
            "Сделай маленький шаг — выбери одно ключевое слово.",
        ]
    },
    2: {
        "phrases": [
            "Я рядом, вместе справимся.",
            "Не сдавайся — иногда трудность значит, что ты растёшь.",
            "Ошибки — это часть процесса, всё идёт нормально.",
            "Подумай: что именно мешает? Мы это разберём."
        ],
        "challenges": [
            "Сделай паузу и попробуй найти одно отличие в примере.",
            "Сравни с предыдущим шагом: что похоже, а что отличается?"
        ]
    },
    3: {
        "phrases": [
            "Очень хорошо идёшь — продолжай!",
            "Ты уже многое понял(а).",
            "Хорошо держишь темп, это радует.",
            "Отлично! Попробуй сам(а) объяснить кратко."
        ],
        "challenges": [
            "Сравни своё решение с другим подходом.",
            "Попробуй объяснить задачу другу (в 2 предложениях)."
        ]
    },
    4: {
        "phrases": [
            "Ты действуешь уверенно — здорово!",
            "Самостоятельность — это круто.",
            "Супер, ты показываешь высокий уровень.",
            "Мне нравится твоя инициатива."
        ],
        "challenges": [
            "Попробуй решить задачу за 1 минуту.",
            "Придумай свой пример и сравни с материалами."
        ]
    }
}

# import os
# import glob

# from typing import List
# from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

def load_documents(discipline: str) -> List[str]:
    """
    Загружает все .txt, .md, .pdf файлы по дисциплине из knowledge_base.
    Возвращает список строк (документов).
    """
    folder = os.path.join("knowledge_base", discipline.lower())
    if not os.path.exists(folder):
        print(f"⚠️ Папка для дисциплины не найдена: {folder}")
        return []

    files = glob.glob(os.path.join(folder, "*"))
    documents = []

    for file_path in files:
        ext = Path(file_path).suffix.lower()
        try:
            if ext in [".txt", ".md"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    documents.append(f.read())
            elif ext == ".pdf" and PdfReader:
                reader = PdfReader(file_path)
                text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                documents.append(text)
            else:
                print(f"🔸 Пропущен неподдерживаемый файл: {file_path}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке {file_path}: {e}")

    print(f"✅ Загружено {len(documents)} документов из {folder}")
    return documents

# 1. Загрузка базы знаний
kb = KnowledgeBase()
kb.load("Цифровая культура")

# 2. Создание Expert и FSM
expert = Expert(kb)
ctx = Context(
    discipline="Цифровая культура",
    lesson_number=2,
    topic="Генерация инфографики",
    student_level=1
)
fsm = TeachingFSM(ctx, expert=expert)

# 3. Симуляция диалога
fsm.handle_event("init")
fsm.handle_event("student_question", "Что такое инфографика?")
fsm.handle_event("student_question", "Где применяется инфографика?")

# 4. Просмотр истории
from pprint import pprint
pprint(ctx.progress["Expert"]["dialog_history"])

# ============================================
# 🎭 Sprint 8.1 — TTS через единый адаптер + EventBus
# (мок-реализация Piper/RHVoice; кэш; эмоции; tts_done/tts_failed)
# ============================================
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import hashlib, io, wave, math, time, random
import numpy as np

# --- 0) Утилиты и слот состояния в Context
def _ensure_tts_slot(context: Context):
    context.progress.setdefault("TTS", {})
    slot = context.progress["TTS"]
    slot.setdefault("cache", {})          # hash -> {"path": "file://...", "sr": 16000, "word_ts": [...], "phonemes": [...]}
    slot.setdefault("dir", "/mnt/data/tts_cache")
    return slot

def _hash_key(text: str, voice: Optional[str], emotion: Optional[str], rate: float) -> str:
    key = f"{text}|{voice or ''}|{emotion or ''}|{rate:.3f}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()

def _save_wav_16k_mono(samples: np.ndarray, path: str, sr: int = 16000):
    # нормализуем в int16
    arr = np.clip(samples, -1.0, 1.0)
    i16 = (arr * 32767).astype(np.int16)
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(i16.tobytes())

# --- 1) Эмоции и темп из Motivator → упрощённая карта
TONE_TO_EMOTION = {
    "warm": "warm",
    "mentor": "warm",
    "partner": "neutral",
    "strict": "calm",
    "нейтральный преподаватель": "neutral"
}
PACE_TO_RATE = {
    "замедленный": 0.9,
    "упрощённый": 0.95,
    "обычный": 1.0,
    "ускоренный": 1.07
}

def pick_emotion_and_rate(context: Context) -> Tuple[str, float]:
    mot = context.progress.get("Motivator", {}).get("last", {})
    style = mot.get("style", {}) if isinstance(mot, dict) else {}
    tone = style.get("tone", "нейтральный преподаватель")
    pace = style.get("pace", "обычный")
    emotion = TONE_TO_EMOTION.get(tone, "neutral")
    rate = PACE_TO_RATE.get(pace, 1.0)
    return emotion, rate

# --- 2) Интерфейс TTS
class BaseTTSAdapter:
    sr: int = 16000

    def synthesize(self, text: str, voice: Optional[str] = None,
                   emotion: Optional[str] = None, rate: float = 1.0) -> Dict[str, Any]:
        """
        ДОЛЖЕН вернуть:
        {
          "wav": bytes,
          "sr": 16000,
          "word_ts": [{"t0": float, "t1": float, "word": str}, ...],
          "phonemes": ["p","a","t",...]
        }
        """
        raise NotImplementedError

# --- 3) Мок-адаптер Piper (генерит синус/ам-паузы; даёт word_ts/phonemes)
class PiperAdapter(BaseTTSAdapter):
    def synthesize(self, text: str, voice=None, emotion=None, rate: float = 1.0) -> Dict[str, Any]:
        sr = self.sr
        # простая длительность: 70 мс на слово * коэффициент / rate
        words = [w for w in text.strip().split() if w]
        base_per_word = 0.07
        dur = max(0.5, len(words) * base_per_word / max(0.5, rate))
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # частота зависит от эмоции
        f0 = {"warm": 180, "neutral": 160, "calm": 140, "excited": 220}.get(emotion or "neutral", 160)
        x = 0.15 * np.sin(2 * math.pi * f0 * t)
        # «паузы» после точек/запятых: сниженная амплитуда
        if "," in text or "." in text:
            x[int(len(x)*0.6):int(len(x)*0.65)] *= 0.2

        # тайминги слов — равномерно
        word_ts = []
        if words:
            word_len = dur / len(words)
            for i, w in enumerate(words):
                t0 = i * word_len
                t1 = (i+1) * word_len
                word_ts.append({"t0": round(t0, 3), "t1": round(t1, 3), "word": w})

        # «фонемы» — грубая схема по буквам (для теста пайплайна)
        raw = "".join([c for c in text.lower() if c.isalpha()])
        phonemes = list(raw[:64])  # ограничим

        # в байты WAV
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes((x * 32767).astype(np.int16).tobytes())
        return {"wav": bio.getvalue(), "sr": sr, "word_ts": word_ts, "phonemes": phonemes}

# --- 4) Мок-адаптер RHVoice (аналогично, чуть другая основа)
class RHVoiceAdapter(BaseTTSAdapter):
    def synthesize(self, text: str, voice=None, emotion=None, rate: float = 1.0) -> Dict[str, Any]:
        sr = self.sr
        words = [w for w in text.strip().split() if w]
        dur = max(0.6, len(words) * 0.08 / max(0.5, rate))
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        f0 = {"warm": 170, "neutral": 150, "calm": 130, "excited": 210}.get(emotion or "neutral", 150)
        # треугольник + лёгкий шум
        tri = 2 * np.abs((t * f0) % 1 - 0.5) - 0.5
        x = 0.12 * tri + 0.02*np.random.randn(len(t))
        # тайминги слов
        word_ts = []
        if words:
            word_len = dur / len(words)
            for i, w in enumerate(words):
                t0 = i * word_len
                t1 = (i+1) * word_len
                word_ts.append({"t0": round(t0, 3), "t1": round(t1, 3), "word": w})
        phonemes = list("".join([c for c in text.lower() if c.isalpha()])[:64])
        # в байты WAV
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        return {"wav": bio.getvalue(), "sr": sr, "word_ts": word_ts, "phonemes": phonemes}

# --- 5) Высокоуровневый фасад TTS с кэшем
class TTSService:
    def __init__(self, adapter: BaseTTSAdapter, default_voice: Optional[str]=None):
        self.adapter = adapter
        self.default_voice = default_voice

    def synthesize(self, context: Context, text: str,
                   voice: Optional[str]=None, emotion: Optional[str]=None, rate: float=1.0) -> Dict[str, Any]:
        slot = _ensure_tts_slot(context)
        key = _hash_key(text, voice or self.default_voice, emotion, rate)

        # короткие фразы — кэшируем (<= 120 символов)
        if len(text) <= 120 and key in slot["cache"]:
            return {"cache_hit": True, **slot["cache"][key]}

        data = self.adapter.synthesize(text=text, voice=voice or self.default_voice, emotion=emotion, rate=rate)

        # сохраняем в файл для Unity (file://)
        path = f'{slot["dir"]}/{key}.wav'
        _save_wav_16k_mono(
            samples=(np.frombuffer(data["wav"], dtype=np.int16).astype(np.float32)/32767.0
                     if isinstance(data["wav"], (bytes, bytearray)) else data["wav"]),
            path=path, sr=data["sr"]
        )
        rec = {"path": f"file://{path}", "sr": data["sr"], "word_ts": data.get("word_ts", []), "phonemes": data.get("phonemes", [])}
        if len(text) <= 120:
            slot["cache"][key] = rec
        return rec

# --- 6) «Сценарист» речи (микро-8.3): собираем intro/core/outro
def build_say_script_from_answer(answer: Dict[str, Any], context: Context) -> Dict[str, Any]:
    # intro/outro — лёгкие, если в ответе есть эмпатия, можно подставить туда;
    # для простоты берём короткие фразы из мотивации
    mot = context.progress.get("Motivator", {}).get("last", {})
    mot_phrase = (mot.get("motivation") or {}).get("phrase")
    intro = None
    if mot_phrase:
        intro = mot_phrase if len(mot_phrase.split()) <= 10 else None

    core = answer.get("answer", "") or ""
    outro = None
    challenge = (mot.get("motivation") or {}).get("challenge")
    if challenge and len(challenge.split()) <= 10:
        outro = challenge

    lines = []
    if intro: lines.append({"role":"intro","text":intro})
    if core:  lines.append({"role":"core","text":core})
    if outro: lines.append({"role":"outro","text":outro})

    # подсказки эмоций/жестов (минимум)
    emotion, _ = pick_emotion_and_rate(context)
    return {"lines": lines, "emotion_hint": emotion, "gesture_hints": []}

# --- 7) Подписчик EventBus: expert_answer -> build_say_script -> TTS -> publish tts_done/tts_failed
def make_expert_answer_handler_tts(tts: TTSService, bus: EventBus):
    def _handler(ev: Event):
        try:
            ans = ev.payload.get("answer", {}) or {}
            text_full = ans.get("answer") or ""
            if not isinstance(text_full, str) or not text_full.strip():
                # ничего синтезировать
                return

            # сценарист: интро/ядро/аутро → склеиваем в одну строку для TTS
            say = build_say_script_from_answer(ans, bus.context)
            text_parts = [seg["text"] for seg in say.get("lines", []) if seg.get("text")]
            text_tts = (" ".join(text_parts)).strip() or text_full.strip()

            # эмоция/скорость из Motivator
            emotion, rate = pick_emotion_and_rate(bus.context)

            # синтез
            out = tts.synthesize(bus.context, text=text_tts, emotion=emotion, rate=rate)

            # публикуем tts_done
            bus.publish(Event(
                type="tts_done",
                source="tts",
                payload={
                    "text": text_tts,
                    "audio": out["path"],         # file://...
                    "sr": out["sr"],
                    "word_ts": out.get("word_ts", []),
                    "phonemes": out.get("phonemes", []),
                    "emotion": emotion
                }
            ))
        except Exception as e:
            bus.publish(Event(
                type="tts_failed",
                source="tts",
                payload={"reason": str(e), "fallback_text": ev.payload.get("answer", {}).get("answer", "")}
            ))
    return _handler

# --- 8) Хелпер: создать сервис и прикрутить к bus
def attach_tts_to_bus(bus: EventBus, engine: str = "piper", default_voice: Optional[str]=None) -> TTSService:
    adapter = PiperAdapter() if engine.lower()=="piper" else RHVoiceAdapter()
    tts = TTSService(adapter=adapter, default_voice=default_voice)
    bus.subscribe("expert_answer", make_expert_answer_handler_tts(tts, bus))

    # базовое логирование
    def _logger(ev: Event):
        print(f"🪵 [LOG] {ev.type} <- {ev.source} :: keys={list(ev.payload.keys())}")
    bus.subscribe("tts_done", _logger)
    bus.subscribe("tts_failed", _logger)
    return tts

# ============================================
# 🔁 Sprint 7.3 — Перезапуск цикла занятия
# ============================================
from typing import Dict, Any, Optional
import copy
import time

# --- 1) Снапшот/реставрация прогресса (бережно) ---

def snapshot_progress(context: Context) -> Dict[str, Any]:
    """
    Делаем неглубокий снимок ключевых модулей; 
    Organizer + Motivator сохраняем полностью; Expert — только метрики/последний ответ.
    """
    p = context.progress
    snap = {
        "Motivator": copy.deepcopy(p.get("Motivator", {})),
        "Organizer": copy.deepcopy(p.get("Organizer", {})),
        "Expert_meta": {
            "engagement": (p.get("Expert", {}) or {}).get("engagement"),
            "confidence": (p.get("Expert", {}) or {}).get("confidence"),
            "latency_avg_sec": (p.get("Expert", {}) or {}).get("latency_avg_sec"),
            "last_answer": (p.get("Expert", {}) or {}).get("last_answer"),
        },
        "Cartographer": copy.deepcopy(p.get("Cartographer", {})),
        "EventBus_log_tail": copy.deepcopy((p.get("EventBus", {}) or {}).get("log", [])[-20:])
    }
    return snap

def restore_progress(context: Context, snap: Dict[str, Any], *, full: bool):
    """
    Возвращаем сохранённые куски прогресса.
    full=True: очищаем историю Expert (диалог), остальное бережём.
    """
    p = context.progress
    p.setdefault("Motivator", {}).update(snap.get("Motivator", {}))
    p.setdefault("Organizer", {}).update(snap.get("Organizer", {}))
    p.setdefault("Cartographer", {}).update(snap.get("Cartographer", {}))

    p.setdefault("Expert", {})
    if full:
        # Полный рестарт: чистим историю диалога, но оставляем полезные метрики
        p["Expert"]["dialog_history"] = []
        p["Expert"]["last_answer"] = None
    # Вернём базовые метрики эксперта
    for k, v in (snap.get("Expert_meta") or {}).items():
        if v is not None:
            p["Expert"][k] = v

# --- 2) Хелперы рестарта этапа/всего занятия ---

def restart_current_stage(conductor: 'Conductor', bus: EventBus, *, reason: str = ""):
    """
    Мягкий перезапуск текущего этапа: 
    - повторно объявляем stage_changed на ту же стадию
    - триггерим базовые действия для этапа (goals/tasks/work/reflection/wrapup)
    """
    stage = conductor.stage
    bus.publish(Event(type="stage_changed", source="conductor", payload={"stage": stage, "reason": reason or "restart_stage"}))

    # Локальные «пере-входы» в этап (то, что вы делали в 7.2)
    if stage == "goals":
        # подсказка Cartographer/Organizer, если нужно
        if 'Organizer' in globals():
            org = Organizer()
            bus.publish(Event(type="expert_answer", source="system", payload={"question": "[auto] цели", "answer": {"note": "refresh goals"}}))
            bus.publish(Event(type="organizer_update", source="organizer", payload={"organizer": org.process(bus.context)}))

    elif stage == "tasks":
        if 'Organizer' in globals():
            org = Organizer()
            bus.publish(Event(type="organizer_update", source="organizer", payload={"organizer": org.process(bus.context)}))

    elif stage == "work":
        # мягкий пинг мотивации на «работу»
        bus.publish(Event(type="motivation_update", source="system", payload={"last": (bus.context.progress.get("Motivator") or {}).get("last", {})}))

    elif stage == "reflection":
        # мягкий рефлексивный вопрос
        bus.publish(Event(type="student_question", source="system", payload={"text": "Давай коротко подумаем: что сейчас мешает двигаться дальше?"}))

    elif stage == "wrapup":
        # сгенерируем свежую краткую сводку (как в 7.2)
        summary = {
            "topic": bus.context.topic,
            "answers_count": len((bus.context.progress.get("Expert", {}) or {}).get("dialog_history", [])),
            "work_turns": 0,  # можно дорассчитать из Conductor
            "tasks_available": bool((bus.context.progress.get("Organizer", {}) or {}).get("tasks")),
            "motivation_level": (bus.context.progress.get("Motivator", {}) or {}).get("level", 1),
            "style": (bus.context.progress.get("Motivator", {}) or {}).get("last", {}).get("style", {})
        }
        bus.publish(Event(type="lesson_finished", source="conductor", payload={"summary": summary}))

def restart_full(conductor: 'Conductor', bus: EventBus, *, reason: str = ""):
    """
    Полный перезапуск занятия:
    - сохраняем прогресс (Motivator/Organizer/метрики)
    - чистим Expert диалог и ставим сцену 'start'
    - снова проводим цели/задания
    """
    ctx = bus.context
    snap = snapshot_progress(ctx)

    # Сброс состояния ведущего цикла
    conductor.stage = "start"
    conductor.answers_count = 0
    conductor.work_turns = 0

    restore_progress(ctx, snap, full=True)

    # Переинициализация пайплайна этапов, как в 7.2
    bus.publish(Event(type="stage_changed", source="conductor", payload={"stage": "goals", "reason": reason or "restart_full"}))
    if 'Organizer' in globals():
        org = Organizer()
        bus.publish(Event(type="organizer_update", source="organizer", payload={"organizer": org.process(ctx)}))
    bus.publish(Event(type="stage_changed", source="conductor", payload={"stage": "tasks"}))

# --- 3) Обработчик события 'restart' для шины ---

def make_restart_handler(conductor: 'Conductor', bus: EventBus):
    def _handler(ev: Event):
        mode = (ev.payload or {}).get("mode", "stage")
        reason = (ev.payload or {}).get("reason", "")
        cur = conductor._stage()  # <-- вместо conductor.stage

        if mode == "full":
            # Сохраняем мотивацию/прогресс, но сбрасываем счётчик work_turns
            slot = bus.context.progress.setdefault("Conductor", {})
            slot["work_turns"] = 0
            slot["summary"] = {}
            # Стадия "start" и стандартный цикл инициализации
            conductor._set_stage("start")  # <-- вместо присваивания .stage
            bus.publish(Event(type="init", source="conductor", payload={"restart": "full", "reason": reason}))
            return {"status": "restarted_full", "stage": conductor._stage()}

        # Частичный перезапуск текущей стадии
        # Просто повторяем входные события стадии
        if cur in {"start", "goals"}:
            goals = _get_or_make_goals(bus.context)
            conductor._set_stage("goals")
            bus.publish(Event(type="goals_ready", source="conductor", payload={"goals": goals, "restart": "stage"}))
        elif cur == "tasks":
            conductor._set_stage("tasks")
            bus.publish(Event(
                type="tasks_ready", source="conductor",
                payload={"has_tasks": conductor._has_tasks(), "restart": "stage"}
            ))
        elif cur == "work":
            # На работе просто мягко «подтолкнём» мотивацию/органайзер при необходимости
            conductor._set_stage("work")
            # Ничего не публикуем — следующий вопрос студента пройдёт обычным маршрутом
        elif cur == "reflection":
            conductor._set_stage("reflection")
            bus.publish(Event(type="ask_reflection", source="conductor",
                              payload={"reason": "restart_stage"}))
        elif cur == "wrapup":
            # Перезапуск «итога» — пересоберём summary
            conductor._set_stage("wrapup")
            conductor._finish()
        else:
            # finished или неизвестная — начинаем сначала
            conductor._set_stage("start")
            bus.publish(Event(type="init", source="conductor", payload={"restart": "from_finished"}))

        return {"status": "restarted_stage", "stage": conductor._stage(), "previous": cur}
    return _handler

# --- 4) Подписка EventBus на 'restart' (разово, после build_event_bus и создания Conductor) ---
# Пример (раскомментируйте, если нужно здесь же):
bus.subscribe("restart", make_restart_handler(conductor, bus))

# --- 5) Мини‑проверка 7.3 (ожидается, что есть bus, conductor, expert, ctx) ---

def test_restart_via_bus(bus: EventBus, conductor: 'Conductor'):
    print("▶️ Старт теста перезапуска")
    print("Текущая стадия:", conductor._stage())   # <- было conductor.stage

    print("\n— Частичный перезапуск текущего этапа")
    bus.publish(Event(type="restart", source="tester",
                      payload={"mode": "stage", "reason": "retry_current"}))
    time.sleep(0.05)

    bus.publish(Event(type="student_question", source="student",
                      payload={"text": "Можно ещё раз про выбор диаграммы?"}))
    time.sleep(0.05)

    print("\n— Полный перезапуск (с начала)")
    bus.publish(Event(type="restart", source="tester",
                      payload={"mode": "full", "reason": "not_understood"}))
    time.sleep(0.05)

    bus.publish(Event(type="student_question", source="student",
                      payload={"text": "Ок, повторим цели занятия кратко?"}))
    time.sleep(0.05)

    from pprint import pprint
    print("\n📜 Хвост EventBus лога:")
    pprint(bus.context.progress["EventBus"]["log"][-8:])
    print("Текущая стадия:", conductor._stage())   # <- было conductor.stage

import json, csv, os, time
from datetime import datetime

def _ts_human(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def export_eventbus_logs(ctx,
                         json_path: str = None,
                         csv_path: str = None,
                         extra_meta: dict = None):
    """Сохраняет EventBus лог + сводные метаданные в JSON/CSV."""
    eb = (ctx.progress.get("EventBus") or {})
    log = eb.get("log", [])
    session_id = eb.get("id", "unknown-session")

    # --- базовые метаданные
    meta = {
        "session_id": session_id,
        "saved_at_ts": time.time(),
        "saved_at": _ts_human(time.time()),
        "discipline": getattr(ctx, "discipline", None),
        "topic": getattr(ctx, "topic", None),
        "lesson_number": getattr(ctx, "lesson_number", None),
    }

    # --- срез по модулям
    expert = ctx.progress.get("Expert", {})
    motiv  = ctx.progress.get("Motivator", {})
    org    = ctx.progress.get("Organizer", {})
    cond   = ctx.progress.get("Conductor", {})

    last_answer = (expert.get("dialog_history") or [])[-1] if expert.get("dialog_history") else None

    meta["modules"] = {
        "Expert": {
            "history_len": len(expert.get("dialog_history", [])),
            "last_question": (last_answer or {}).get("question"),
            "last_intents": (last_answer or {}).get("intents"),
            "last_detail":  (last_answer or {}).get("detail"),
        },
        "Motivator": {
            "level": motiv.get("level"),
            "last":  motiv.get("last"),
            "drop_count": ctx.progress.get("Motivator", {}).get("drop_count", 0),
        },
        "Organizer": {
            "tasks_count": len((org.get("tasks") or [])) if isinstance(org.get("tasks"), list) else None,
        },
        "Conductor": {
            "stage": cond.get("stage"),
            "work_turns": cond.get("work_turns"),
            "summary": cond.get("summary"),
        }
    }

    if extra_meta:
        meta.update({"extra": extra_meta})

    # --- JSON (полный)
    if json_path is None:
        json_path = f"./logs_{session_id}_{int(time.time())}.json"

    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "eventbus_log": log}, f, ensure_ascii=False, indent=2)

    # --- CSV (плоский хвост событий)
    if csv_path is None:
        csv_path = f"./logs_{session_id}_{int(time.time())}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts","ts_human","type","source","payload_keys"])
        writer.writeheader()
        for rec in log:
            writer.writerow({
                "ts": rec.get("ts"),
                "ts_human": _ts_human(rec.get("ts")),
                "type": rec.get("type"),
                "source": rec.get("source"),
                "payload_keys": ",".join(rec.get("payload_keys", [])),
            })

    print(f"✅ Сохранено:\n- JSON: {json_path}\n- CSV:  {csv_path}")
    return {"json": json_path, "csv": csv_path, "meta": meta}

# Пример вызова:
# export_eventbus_logs(ctx)

# ============================================
# 🧪 Sprint 7.4 — Сценарные прогоны и отладка
# Требования: уже созданы ctx, expert, motivator, (organizer), bus, conductor
# ============================================
from pprint import pprint
import time, random

def _tail_log(n=10):
    return ctx.progress.get("EventBus", {}).get("log", [])[-n:]

def _stage():
    return ctx.progress.get("Conductor", {}).get("stage")

def _mot():
    return ctx.progress.get("Motivator", {}).get("last", {})

def _org_has_tasks():
    org = ctx.progress.get("Organizer", {})
    return bool(org.get("tasks"))

def _answers_count():
    return len(ctx.progress.get("Expert", {}).get("dialog_history", []))

def _reset_for_scenario():
    # мягкая очистка только нужных частей, без сноса индекса/KB
    ctx.progress["EventBus"]["log"] = []
    ctx.progress["Conductor"]["work_turns"] = 0
    ctx.progress["Conductor"]["summary"] = {}
    ctx.progress["Conductor"]["stage"] = "start"
    ctx.progress.setdefault("Reflection", {})["asked"] = []
    # не трогаем историю Expert/Motivator — хотим смотреть кумулятивно
    bus.publish(Event(type="init", source="tester", payload={}))

def _print_header(title):
    print("\n" + "="*6, title, "="*6)

# ---------- Сценарий 1: Всё идёт гладко ----------
def scenario_smooth():
    _print_header("Сценарий 1: всё идёт гладко")
    _reset_for_scenario()

    # goals -> tasks -> work движется автоматически через Conductor.on_init
    # Работа: 2 содержательных вопроса
    bus.publish(Event(type="student_question", source="student",
                      payload={"text": "С чего начать подготовку данных для инфографики?"}))
    time.sleep(0.05)
    bus.publish(Event(type="student_question", source="student",
                      payload={"text": "Как выбрать подходящий тип диаграммы для сравнения?"}))
    time.sleep(0.05)

    # Ответ рефлексии
    bus.publish(Event(type="student_reflection", source="student",
                      payload={"text": "Немного волновался, но стало понятнее."}))
    time.sleep(0.05)

    print("Стадия:", _stage())
    print("Ответов эксперта:", _answers_count())
    print("Есть задания от Organizer:", _org_has_tasks())
    print("Motivator:", {k:_mot().get(k) for k in ["level","level_name","style"]})
    print("Хвост лога:")
    pprint(_tail_log(6))

# ---------- Сценарий 2: Студент часто ошибается ----------
def scenario_mistakes():
    _print_header("Сценарий 2: частые ошибки/сомнения")
    _reset_for_scenario()

    bad_prompts = [
        "Я ошибся с подписями…",
        "Не понимаю, почему неверно позиционируются метки",
        "Наверное, опять неправильно сделал",
        "Хм…"
    ]
    for q in bad_prompts:
        bus.publish(Event(type="student_question", source="student", payload={"text": q}))
        time.sleep(0.05)

    mot = _mot()
    print("Стадия:", _stage())
    print("Ответов эксперта:", _answers_count())
    print("Motivator level:", mot.get("level"), mot.get("level_name"))
    print("Сигналы:", mot.get("signals"))
    print("Счётчик падений (drop_count):", mot.get("drop_count"))
    print("Хвост лога:")
    pprint(_tail_log(6))

# ---------- Сценарий 3: Потеря мотивации ----------
def scenario_low_motivation():
    _print_header("Сценарий 3: падение мотивации")
    _reset_for_scenario()

    # 1) длинная пауза/низкие метрики (имитируем через Expert‑метрики)
    ex = ctx.progress.setdefault("Expert", {})
    ex["engagement"] = 0.32
    ex["confidence"] = 0.28
    ex["latency_sec"] = 50.0  # Имитируем медленный отклик (учтётся Motivator-ом)

    # 2) короткие/неуверенные ответы
    for q in ["Да", "Не понимаю", "Хм…"]:
        bus.publish(Event(type="student_question", source="student", payload={"text": q}))
        time.sleep(0.05)

    mot = _mot()
    print("Стадия:", _stage())
    print("Ответов эксперта:", _answers_count())
    print("Motivator level:", mot.get("level"), mot.get("level_name"))
    print("Сигналы:", mot.get("signals"))
    print("Реакция:", mot.get("reaction"))
    print("Стиль базовый:", mot.get("style"))
    print("Стиль update:", mot.get("style_update"))
    print("Счётчик падений:", mot.get("drop_count"))
    print("Хвост лога:")
    pprint(_tail_log(6))

# ---------- Сценарий 4: Перезапуск пары ----------
def scenario_restart():
    _print_header("Сценарий 4: перезапуск")
    _reset_for_scenario()

    # Немного «работы»
    bus.publish(Event(type="student_question", source="student", payload={"text": "Как оформить легенду к диаграмме?"}))
    time.sleep(0.05)

    # Частичный рестарт текущего этапа
    bus.publish(Event(type="restart", source="tester", payload={"mode": "stage", "reason": "retry_current"}))
    time.sleep(0.05)
    bus.publish(Event(type="student_question", source="student", payload={"text": "Ещё раз: где подписывать значения?"}))
    time.sleep(0.05)

    # Полный рестарт с начала
    bus.publish(Event(type="restart", source="tester", payload={"mode": "full", "reason": "not_understood"}))
    time.sleep(0.05)
    bus.publish(Event(type="student_question", source="student", payload={"text": "Повтори кратко цели занятия, пожалуйста."}))
    time.sleep(0.05)

    print("Стадия:", _stage())
    print("Ответов эксперта:", _answers_count())
    print("Motivator level:", _mot().get("level"), _mot().get("level_name"))
    print("Хвост лога:")
    pprint(_tail_log(8))

# ---------- Запуск всех ----------
def run_all_scenarios():
    print("ℹ️ Используем ctx/expert/bus/conductor (и motivator/organizer, если есть).")
    scenario_smooth()
    scenario_mistakes()
    scenario_low_motivation()
    scenario_restart()

# ▶️ Запуск
run_all_scenarios()
paths = export_eventbus_logs(ctx)
paths

print("🎯 Мини‑тест TTS-пайплайна")
bus.publish(Event(type="student_question", source="student", payload={"text": "Как выбрать тип диаграммы для сравнения?"}))
time.sleep(0.1)

# посмотрим хвост event-лога
from pprint import pprint
print("\n📜 Хвост EventBus:")
pprint(ctx.progress["EventBus"]["log"][-6:])

# и что сохранил TTS
print("\n🗂 Пример записи в TTS cache (если была короткая фраза):")
print(list(ctx.progress.get("TTS", {}).get("cache", {}).keys())[:2])

# чтобы увидеть последнюю дорожку:
# открой путь из последнего tts_done (если логируешь payload где-то)