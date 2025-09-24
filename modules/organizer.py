# modules/organizer.py

import uuid

def generate_tasks(goals: dict) -> list:
    tasks = []

    for i, subgoal in enumerate(goals.get("subgoals", []), 1):
        subgoal_lower = subgoal.lower()

        # Определяем тип задания
        if any(word in subgoal_lower for word in ["объяснить", "описать", "перечислить"]):
            task_type = "text"
            hints = ["Используй термины из лекции", "Приведи простой пример"]
            criteria = ["Наличие ключевых понятий", "Связность объяснения"]
        elif any(word in subgoal_lower for word in ["применить", "создать", "выполнить", "построить"]):
            task_type = "action"
            hints = ["Вспомни алгоритм из базы знаний", "Сделай по шагам"]
            criteria = ["Завершённость работы", "Соответствие требованиям"]
        elif any(word in subgoal_lower for word in ["оценить", "анализировать", "сравнить", "обосновать"]):
            task_type = "reflection"
            hints = ["Сравни два варианта", "Объясни свой выбор"]
            criteria = ["Обоснованность", "Логичность рассуждений"]
        else:
            task_type = "text"
            hints = ["Начни с базового объяснения"]
            criteria = ["Понятность ответа"]

        task = {
            "id": f"task_{i}",
            "goal": subgoal,
            "type": task_type,
            "instruction": f"Задание: {subgoal}",
            "hints": hints,
            "evaluation_criteria": criteria,
            "start_time": None,
            "status": "not_started",  # новый статус
            "end_time": None,
            "duration_sec": None,
            "is_completed": False,
            "student_answer": None    # поле для хранения ответа
        }

        tasks.append(task)

    return tasks

class Organizer(TeachingFunction):
    def process(self, context: Context) -> dict:
        print(f"[Organizer] Генерация заданий по теме: {context.topic}")

        goals = context.progress.get("Cartographer", {}).get("goals")
        if not goals:
            return {"error": "Цели не найдены. Сначала вызовите Cartographer."}

        tasks = generate_tasks(goals)

        # Сохраняем в контекст
        context.update_progress("Organizer", {
            "tasks": tasks
        })

        return context.progress["Organizer"]