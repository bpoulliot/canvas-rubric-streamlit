from canvasapi import Canvas

class CanvasClient:
    """
    Wrapper around Canvas API client.
    Stores base_url and api_key explicitly to avoid
    accessing private CanvasAPI internals.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.canvas = Canvas(self.base_url, self.api_key)

    def get_account(self, account_id: int):
        return self.canvas.get_account(account_id)
