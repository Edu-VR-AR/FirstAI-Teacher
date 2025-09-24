# core/fsm.py

class TeachingFSM:
    def __init__(self, context: Context, expert: 'Expert' = None):
        self.context = context
        self.state = "start"
        self.expert = expert

    def handle_event(self, event: str, data: str = None):
        print(f"\n📍 Событие: {event}, текущее состояние: {self.state}")

        # --- автозапуск: если студент задаёт вопрос в самом начале
        if self.state == "start" and event == "student_question":
            # сначала инициализируем занятие
            self.handle_event("init")
            # и повторяем вопрос уже в новом состоянии
            return self.handle_event("student_question", data)

        if self.state == "start" and event == "init":
            self.state = "goals"
            result = Cartographer().process(self.context)
            self.context.update_progress("Cartographer", result)
            return

        elif self.state in ["goals", "task", "expertise"] and event == "student_question":
            self.state = "expertise"
            if self.expert:
                answer = self.expert.respond(data, self.context)
                # печать — с учётом сброса
                if isinstance(answer, dict) and answer.get("status") == "dialog_cleared":
                    print("🗑 Память эксперта очищена.\n")
                else:
                    print(f"\n💬 Expert ответил:\n{answer['answer']}\n")
            else:
                print("⚠️ Expert не подключен")
            return

        elif self.state == "expertise" and event in ["timeout", "inactivity"]:
            self.state = "motivation"
            result = Motivator().process(self.context)
            self.context.update_progress("Motivator", result)
            return
        
        #####
        elif event == "student_reflection":
            answer_text = kwargs.get("text", "")
            return self.motivator.record_reflection_answer(context, answer_text)
        #####        

        elif event == "end":
            self.state = "finish"
            print("🎓 Занятие завершено.")
            return

        else:
            print("⚠️ Событие не распознано или переход невозможен.")

# Патчим FSM так, чтобы после Expert.answer прогонять через тюнер
# (если FSM уже определён — переопределим только handle_event; при необходимости верни старую версию)
old_TeachingFSM = TeachingFSM

class TeachingFSM(old_TeachingFSM):
    def handle_event(self, event: str, data: str = None):
        print(f"\n📍 Событие: {event}, текущее состояние: {self.state}")

        # автозапуск
        if self.state == "start" and event == "student_question":
            self.handle_event("init")
            return self.handle_event("student_question", data)

        if self.state == "start" and event == "init":
            self.state = "goals"
            result = Cartographer().process(self.context)
            self.context.update_progress("Cartographer", result)
            return

        elif self.state in ["goals", "task", "expertise"] and event == "student_question":
            self.state = "expertise"
            if self.expert:
                answer = self.expert.respond(data, self.context)

                # печать: учтём сброс диалога
                if isinstance(answer, dict) and answer.get("status") == "dialog_cleared":
                    print("🗑 Память эксперта очищена.\n")
                    return

                # эмпатическая вставка
                enriched = tuner.embellish(answer, self.context, user_text=data)
                # сохраним последний эмпатичный ответ (по желанию)
                self.context.progress.setdefault("RelationalTuner", {})
                self.context.progress["RelationalTuner"]["last"] = enriched["empathy"]

                print(f"\n💬 Expert ответил (empathy):\n{enriched['answer_empathic']}\n")
            else:
                print("⚠️ Expert не подключен")
            return

        elif self.state == "expertise" and event in ["timeout", "inactivity"]:
            self.state = "motivation"
            result = Motivator().process(self.context)
            self.context.update_progress("Motivator", result)
            return
        
        #####
        elif event == "student_reflection":
            # ожидаем, что data — это текст ответа студента
            text = data if isinstance(data, str) else ""
            if hasattr(self, "motivator") and self.motivator:
                out = self.motivator.record_reflection_answer(ctx, text)
                print(f"📝 Рефлексия записана: {text}")
                return out
            else:
                return {"status": "error", "reason": "motivator_not_attached"}
        #####
        

        elif event == "end":
            self.state = "finish"
            # при завершении — мягкая «end»-реплика
            end_stub = {"question": "завершение", "answer": "До встречи на следующем занятии!"}
            enriched = tuner.embellish(end_stub, self.context, user_text="конец сессии", tone_override="warm", position="outro")
            print("🎓 Занятие завершено.\n" + enriched["answer_empathic"])
            return

        else:
            print("⚠️ Событие не распознано или переход невозможен.")
            return