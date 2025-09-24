# modules/knowledge_base.py
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# NLTK: русские стоп-слова
try:
    from nltk.corpus import stopwords  # type: ignore
    import nltk  # type: ignore
    try:
        _ = stopwords.words("russian")
    except LookupError:
        nltk.download("stopwords")
except Exception:
    # Если nltk не установлен (или офлайн первый запуск) — работаем без стоп-слов
    stopwords = None

RU_STOP = None
if stopwords:
    try:
        RU_STOP = set(stopwords.words("russian"))
        RU_STOP.update({"это", "нею"})
    except Exception:
        RU_STOP = None


class KnowledgeBase:
    """
    Простейшая TF-IDF база знаний:
    - load(discipline_path) собирает .txt|.md из папки
    - index() строит векторизатор
    - search(query, top_k) возвращает топ документов с весами
    """

    def __init__(self) -> None:
        self.docs: List[str] = []
        self.doc_names: List[str] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.doc_vectors = None

    def load(self, path: str | Path) -> int:
        p = Path(path)
        files = []
        if p.is_dir():
            files = sorted([*p.glob("**/*.txt"), *p.glob("**/*.md")])
        elif p.is_file():
            files = [p]
        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = fp.read_text(encoding="cp1251", errors="ignore")
            self.docs.append(text)
            self.doc_names.append(fp.name)
        return len(self.docs)

    def index(self) -> None:
        self.vectorizer = TfidfVectorizer(stop_words=list(RU_STOP) if RU_STOP else None)
        self.doc_vectors = self.vectorizer.fit_transform(self.docs)

    def ensure_ready(self) -> None:
        if self.vectorizer is None or self.doc_vectors is None:
            self.index()

    def search(self, query: str, top_k: int = 2) -> List[Tuple[str, str, float]]:
        if not self.docs:
            return []
        self.ensure_ready()
        assert self.vectorizer is not None and self.doc_vectors is not None
        qv = self.vectorizer.transform([query])
        scores = (qv @ self.doc_vectors.T).toarray()[0]
        idx = np.argsort(scores)[::-1][:top_k]
        return [(self.docs[i], self.doc_names[i], float(scores[i])) for i in idx]