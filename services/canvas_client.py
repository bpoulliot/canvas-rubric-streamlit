from canvasapi import Canvas


class CanvasClient:
    def __init__(self, base_url: str, api_key: str):
        self.canvas = Canvas(base_url, api_key)

    def get_account(self, account_id: int):
        return self.canvas.get_account(account_id)
