class CLINotifier:
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

    def send_message(self, message: str, user_id: str = None) -> None:
        print(message)

    def display_progress(self, message: str) -> None:
        print(message)
