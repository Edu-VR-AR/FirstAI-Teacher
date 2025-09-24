# core/context.py

class Context:
    def __init__(self, 
                 discipline: str,
                 lesson_number: int,
                 topic: str,
                 student_level: int,
                 mode: str = "live",
                 student_id: str = None,
                 task_id: str = None,
                 input_type: str = None,
                 data: str = None):
        self.discipline = discipline
        self.lesson_number = lesson_number
        self.topic = topic
        self.student_level = student_level
        self.mode = mode  # "live" или "async"
        self.student_id = student_id
        self.task_id = task_id
        self.input_type = input_type  # например, "pdf", "image", "url", "docx", "text"
        self.data = data  # путь к файлу или URL
        self.progress = {}  # словарь с результатами от модулей

    def update_progress(self, module_name: str, result: dict):
        """Обновляет прогресс работы одного из модулей."""
        self.progress[module_name] = result

    def to_dict(self):
        """Для сериализации/логирования."""
        return {
            "discipline": self.discipline,
            "lesson_number": self.lesson_number,
            "topic": self.topic,
            "student_level": self.student_level,
            "mode": self.mode,
            "student_id": self.student_id,
            "task_id": self.task_id,
            "input_type": self.input_type,
            "data": self.data,
            "progress": self.progress,
        }