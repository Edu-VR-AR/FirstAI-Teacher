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