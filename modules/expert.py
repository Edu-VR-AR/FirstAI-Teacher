# modules/expert.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

from core.context import Context
from .knowledge_base import KnowledgeBase

FACT_TRIGGERS = ["это", "называется", "является", "определяется как"]
PROCEDURE_TRIGGERS = ["сделайте", "выполните", "используйте", "шаг", "процесс", "алгоритм", "нужно"]
META_TRIGGERS = ["оцените", "сравните", "выберите", "зачем", "почему", "что лучше", "преимущество"]


@dataclass
class Answer:
    answer: str
    explanation: str
    sources: List[str]
    next_steps: List[str]


class Expert:
    def __init__(self, kb_path: str | None = None) -> None:
        self.kb = KnowledgeBase()
        if kb_path:
            self.kb.load(kb_path)
            if self.kb.docs:
                self.kb.index()

    def _classify(self, q: str) -> str:
        s = q.lower()
        if any(t in s for t in PROCEDURE_TRIGGERS): return "how"
        if any(t in s for t in META_TRIGGERS): return "why"
        return "fact"

    def _answer_from_docs(self, query: str) -> tuple[str, list[str]]:
        hits = self.kb.search(query, top_k=2) if self.kb.docs else []
        snippets = []
        src = []
        for doc, name, _ in hits:
            snippets.append(doc.strip().splitlines()[0][:300])
            src.append(name)
        text = " ".join(snippets) if snippets else "Пока нет подходящих материалов в базе."
        return text, src

    # упрощённый интерфейс для совместимости с патчем и старым кодом
    def respond(self, context: Context) -> str:
        data = self.process(context)
        return data.get("answer", "")

    def process(self, context: Context) -> Dict:
        q = context.last_user_question or "Расскажи кратко по теме."
        mode = self._classify(q)
        body, src = self._answer_from_docs(q)
        ans = Answer(
            answer=body,
            explanation=f"Тип вопроса: {mode}. Ответ сформирован из ближайших фрагментов базы знаний.",
            sources=src,
            next_steps=["Уточни вопрос", "Добавь материалы в базу знаний", "Запусти следующее задание"]
        )
        return {"answer": ans.answer, "explanation": ans.explanation, "sources": ans.sources, "next_steps": ans.next_steps}