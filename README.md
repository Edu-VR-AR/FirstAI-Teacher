# FirstAI Teacher — Refactored Version

Это перенос ИИ-преподавателя из Jupyter в модульную Python-структуру.
Проект работает через FSM и EventBus, и включает модули: Expert, Organizer, Motivator и др.

## 📦 Установка и запуск

### 1. Установи Python 3.10+
Скачай с [python.org](https://www.python.org/downloads/)

### 2. Создай виртуальную среду
```bash
python -m venv venv
```

### 3. Активируй её

**Windows:**
```bash
.\venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### 4. Установи зависимости
```bash
pip install -r requirements.txt
```

### 5. Запусти проект
```bash
python main.py
```

### Общий порядок запуска:
```
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## 📁 Структура проекта

- `main.py` — точка входа
- `core/` — FSM, Context, EventBus
- `modules/` — преподавательские функции
- `utils/` — TTS, голос, логирование (можно добавить)
- `assets/` — база знаний и вспомогательные файлы

## 🗣 Возможности

- FSM-сценарии обучения
- Генерация целей, заданий, ответов
- Поддержка мотивации и рефлексии
- Эмпатическая коммуникация

## 🚀 Планы расширения

- Голосовой ввод (через `vosk`)
- Озвучка ответов (через `pyttsx3`, `piper` или `TTS`)
- Интеграция с Unity через WebSocket или файл

---

Создано с ❤️ при поддержке ChatGPT-4 и твоего мастерства.