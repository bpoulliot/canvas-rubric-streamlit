from canvasapi.exceptions import ResourceDoesNotExist
from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


EXCLUDED_ACCOUNT_TERMS = [
    "blueprint",
    "@uccs.edu",
    "canvas demo courses",
    "self-enroll",
    "committees",
    "templates",
    "template",
    "zoom testing",
    "manually",
    "permanent",
    "special",
    "no announcements"
]


class CourseService:

    def __init__(self, canvas_client):
        self.client = canvas_client
        self.canvas = canvas_client.canvas

    # ---------------------------------------------------
    # Use /api/v1/manageable_accounts
    # ---------------------------------------------------

    @retry()
    def get_all_accounts(self):
        global_rate_limiter.wait()

        accounts = list(self.canvas.get_manageable_accounts())

        filtered_accounts = []

        for account in accounts:
            name_lower = account.name.lower()
            if any(term in name_lower for term in EXCLUDED_ACCOUNT_TERMS):
                continue
            filtered_accounts.append(account)

        def account_sort_key(account):
            name = account.name.lower()

            if "_college" in name:
                group = 0
            elif ": college" in name or ": school" in name or ": cross" in name:
                group = 1
            elif "archive" in name:
                group = 3
            else:
                group = 2

            return (group, name)

        filtered_accounts.sort(key=account_sort_key)
        return filtered_accounts

    # ---------------------------------------------------
    # Root Term Retrieval
    # ---------------------------------------------------

    @retry()
    def get_root_terms(self):
        global_rate_limiter.wait()
        root_account = self.canvas.get_account(1)
        return list(root_account.get_enrollment_terms())

    # ---------------------------------------------------
    # Course Retrieval
    # ---------------------------------------------------

    @retry()
    def get_courses(self, account_id, pull_type, term_id=None):
        try:
            global_rate_limiter.wait()
            account = self.canvas.get_account(account_id)

            kwargs = {
                "state": ["available"],
                "published": True,
                "blueprint": False,
                "per_page": 100
            }

            if pull_type == "Term":
                if not term_id:
                    raise ValueError("Term must be selected.")
                kwargs["enrollment_term_id"] = term_id

            courses = account.get_courses(**kwargs)
            return list(courses)

        except ResourceDoesNotExist:
            raise ValueError("Canvas returned 'Not Found'. Verify account access.")
