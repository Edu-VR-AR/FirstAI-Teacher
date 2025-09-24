# core/input_handler.py

class InputHandler:
    @staticmethod
    def process(context: Context):
        """Заглушка для обработки внешних данных."""
        print(f"[InputHandler] Получен input_type: {context.input_type}")
        print(f"[InputHandler] Обработка будет реализована позже.")
        return {"status": "not_implemented", "data": None}