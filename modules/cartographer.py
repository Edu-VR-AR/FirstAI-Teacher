# modules/cartographer.py

class TeachingFunction:
    def process(self, context: Context) -> dict:
        raise NotImplementedError("Метод process должен быть переопределён")

# 📌 ВНЕ КЛАССА — генератор целей по уровням Bloom/SoLO
def generate_goals(topic: str, docs: list) -> dict:
    return {
        "main_goal": f"Изучить тему: {topic}",
        "subgoals": [
            f"Объяснить ключевые понятия, связанные с темой «{topic}»",
            f"Применить знания для выполнения задания по теме",
            f"Оценить примеры/результаты на основе полученных знаний"
        ],
        "level": "понимание → применение → оценка"
    }

def generate_text_map(goals: dict, knowledge_types: dict) -> str:
    lines = []
    lines.append(f"🎯 Главная цель занятия: {goals['main_goal']}")
    lines.append("\n📚 Подцели:")
    for i, g in enumerate(goals["subgoals"], 1):
        lines.append(f"  {i}. {g}")

    lines.append(f"\n📈 Уровень сложности: {goals['level']}")
    
    lines.append("\n🔍 Типы знаний:")
    if knowledge_types.get("facts"):
        lines.append("  📘 Факты:")
        for fact in knowledge_types["facts"]:
            lines.append(f"    - {fact}")
    if knowledge_types.get("procedures"):
        lines.append("  🛠 Процедуры:")
        for proc in knowledge_types["procedures"]:
            lines.append(f"    - {proc}")
    if knowledge_types.get("meta"):
        lines.append("  🧠 Мета-знания:")
        for meta in knowledge_types["meta"]:
            lines.append(f"    - {meta}")
    
    return "\n".join(lines)

# 📦 Класс Cartographer, вызывающий функцию generate_goals
class Cartographer(TeachingFunction):
    def process(self, context: Context) -> dict:
        print(f"[Cartographer] Построение целей и структуры по теме: {context.topic}")

        # Загрузка базы знаний
        docs = load_documents(context.discipline)
        if not docs:
            return {"error": "база знаний не найдена или пуста"}

        # Генерация целей
        goals = generate_goals(context.topic, docs)

        # Определение типов знаний
        knowledge_types = extract_knowledge_types(docs)

        # Генерация текстовой карты
        text_map = generate_text_map(goals, knowledge_types)

        # Сохраняем в контекст
        context.update_progress("Cartographer", {
            "doc_count": len(docs),
            "goals": goals,
            "knowledge_types": knowledge_types,
            "text_map": text_map
        })

        return context.progress["Cartographer"]