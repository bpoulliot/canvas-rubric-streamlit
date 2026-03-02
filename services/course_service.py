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

    # ---------------------------------------------------
    # FAST Account Retrieval (No Course Enumeration)
    # ---------------------------------------------------

    @retry()
    def get_all_accounts(self):
        """
        Efficiently retrieves all root accounts and subaccounts
        without enumerating courses.
        """

        global_rate_limiter.wait()

        root_accounts = list(self.client.canvas.get_accounts())
        all_accounts = []

        for root in root_accounts:
            all_accounts.append(root)

            try:
                global_rate_limiter.wait()
                subaccounts = list(root.get_subaccounts(recursive=True))
                all_accounts.extend(subaccounts)
            except Exception:
                continue

        # -----------------------------------------------
        # Filter excluded terms
        # -----------------------------------------------

        filtered_accounts = []

        for account in all_accounts:
            name_lower = account.name.lower()

            if any(term in name_lower for term in EXCLUDED_ACCOUNT_TERMS):
                continue

            filtered_accounts.append(account)

        # -----------------------------------------------
        # Group + Order
        # -----------------------------------------------

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
        root_account = self.client.get_account(1)
        return list(root_account.get_enrollment_terms())

    # ---------------------------------------------------
    # Course Retrieval
    # ---------------------------------------------------

    @retry()
    def get_courses(self, account_id, pull_type, term_id=None):

        try:
            global_rate_limiter.wait()
            account = self.client.get_account(account_id)

            if pull_type == "Term":
                if not term_id:
                    raise ValueError("Term must be selected.")

                courses = account.get_courses(
                    enrollment_term_id=term_id,
                    state=["available"]
                )

            elif pull_type == "Entire Account":
                courses = account.get_courses(
                    state=["available"]
                )

            else:
                raise ValueError("Invalid pull_type")

            return list(courses)

        except ResourceDoesNotExist:
            raise ValueError(
                "Canvas returned 'Not Found'. Verify account access."
            )

    # ---------------------------------------------------
    # Course Filtering
    # ---------------------------------------------------

    def filter_courses(self, courses):

        filtered = []

        for course in courses:

            if course.workflow_state != "available":
                continue

            global_rate_limiter.wait()
            assignments = list(course.get_assignments())

            if not assignments:
                continue

            filtered.append(course)

        return filtered
