# modules/expert.py

# --- вспомогательная функция для сброса диалога (по желанию можно дергать из FSM)
def reset_dialog(context: Context):
    context.progress.setdefault("Expert", {})
    context.progress["Expert"]["dialog_history"] = []
    context.progress["Expert"]["last_answer"] = None
    return {"status": "dialog_cleared", "message": "🗑 Память эксперта очищена."}

# --- Расширенный Expert с поддержкой 5.4
import re, time, random

class Expert(TeachingFunction):
    def __init__(self, kb: 'KnowledgeBase'):
        self.kb = kb

    # --- Внутренние утилиты ---
    def _ensure_history(self, context: Context):
        context.progress.setdefault("Expert", {})
        context.progress["Expert"].setdefault("dialog_history", [])
        context.progress["Expert"].setdefault("last_answer", None)
        context.progress["Expert"].setdefault("engagement", 0.5)  # вовлечённость
        context.progress["Expert"].setdefault("confidence", 0.5)  # уверенность
        context.progress["Expert"].setdefault("tone", "дружелюбный")
        context.progress["Expert"].setdefault("last_interaction_time", time.time())

    def _is_followup(self, question: str) -> bool:
        q = question.strip().lower()
        if len(q.split()) <= 4: return True
        if re.match(r"^(а|и)\b", q): return True
        if re.search(r"\b(подробнее|поясни|уточни|разверни)\b", q): return True
        return False

    # --- Анализ эмоциональных сигналов студента ---
    def _update_metrics(self, question: str, context: Context):
        q = question.lower()
        engagement = context.progress["Expert"]["engagement"]
        confidence = context.progress["Expert"]["confidence"]

        # Время ответа (если студент отвечает быстро → вовлечённость ↑)
        now = time.time()
        last_time = context.progress["Expert"].get("last_interaction_time", now)
        delta = now - last_time
        context.progress["Expert"]["last_interaction_time"] = now
        if delta < 15: engagement += 0.05
        else: engagement -= 0.05

        # Ключевые слова — корректировка уверенности
        if any(word in q for word in ["не понимаю", "сложно", "устал", "плохо"]):
            confidence -= 0.1
        if any(word in q for word in ["получилось", "спасибо", "понятно", "легко"]):
            confidence += 0.1

        # Ограничиваем в диапазоне 0–1
        context.progress["Expert"]["engagement"] = min(max(engagement, 0), 1)
        context.progress["Expert"]["confidence"] = min(max(confidence, 0), 1)

    # --- Подстройка подачи материала ---
    def _adapt_style(self, context: Context):
        conf = context.progress["Expert"]["confidence"]
        if conf < 0.3:
            return "упрощённый", "дружелюбный наставник"
        elif conf > 0.7:
            return "ускоренный", "партнёр по проекту"
        else:
            return "обычный", "нейтральный преподаватель"

    # --- Основной ответ ---
    def respond(self, question: str, context: Context) -> dict:
        print(f"[Expert] Вопрос: {question}")
        self._ensure_history(context)

        # --- сброс памяти
        if question.strip().lower() in {"сброс", "reset", "очистить память"}:
            return reset_dialog(context)

        # обновляем метрики
        self._update_metrics(question, context)

        # определяем намерения и детализацию
        intents = detect_intents(question)
        detail = detect_detail_level(question)

        # поддержка цепочек рассуждений
        history = context.progress["Expert"]["dialog_history"]
        augmented_query, in_reply_to = question, None
        if history and self._is_followup(question):
            last = history[-1]
            in_reply_to = last.get("question")
            prev_snippet = (last.get("answer") or "")[:200]
            augmented_query = f"{in_reply_to}. {question}. Контекст: {prev_snippet}"

        # поиск по базе знаний
        results = self.kb.search(augmented_query, top_k=2)
        if not results:
            base = "Извините, в базе знаний нет информации по этому вопросу."
            sources = []
        else:
            combined_text = "\n".join([doc for doc, _, _ in results])
            base = f"На основе материалов курса:\n{combined_text[:800]}..."
            sources = [name for _, name, _ in results]

        # адаптация подачи
        pace, tone = self._adapt_style(context)

        # финальная сборка ответа
        answer = make_brief(base, 300) if detail == "short" else base
        explanation = make_explanation(base, intents, detail)
        next_steps = build_next_steps(intents, context)

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
            "engagement": context.progress["Expert"]["engagement"],
            "confidence": context.progress["Expert"]["confidence"]
        }

        # сохраняем историю
        history.append(answer_data)
        context.progress["Expert"]["last_answer"] = answer_data
        return answer_data