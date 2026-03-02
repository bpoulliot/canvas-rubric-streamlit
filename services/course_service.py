from canvasapi.exceptions import ResourceDoesNotExist
from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class CourseService:

    def __init__(self, canvas_client):
        self.client = canvas_client

    @retry()
    def get_all_accounts(self):
        global_rate_limiter.wait()
        accounts = list(self.client.canvas.get_accounts())

        all_accounts = []

        for account in accounts:
            all_accounts.append(account)
            try:
                subaccounts = list(account.get_subaccounts(recursive=True))
                all_accounts.extend(subaccounts)
            except Exception:
                pass

        return all_accounts

    @retry()
    def get_terms(self, account_id):
        global_rate_limiter.wait()
        account = self.client.get_account(account_id)
        return list(account.get_enrollment_terms())

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
                "Canvas returned 'Not Found'. Verify account access and token permissions."
            )

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
