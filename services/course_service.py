from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class CourseService:

    def __init__(self, canvas_client):
        self.client = canvas_client

    @retry()
    def get_terms(self, account_id):
        global_rate_limiter.wait()
        account = self.client.get_account(account_id)
        return list(account.get_enrollment_terms())

    @retry()
    def get_subaccounts(self, account_id):
        global_rate_limiter.wait()
        account = self.client.get_account(account_id)
        return list(account.get_subaccounts(recursive=True))

    @retry()
    def get_courses(self, account_id, pull_type, subaccount_id=None, term_id=None):
        global_rate_limiter.wait()
        account = self.client.get_account(account_id)

        if pull_type == "Subaccount":
            subaccount = account.get_subaccount(subaccount_id)
            courses = subaccount.get_courses(state=["available"])
        elif pull_type == "Term":
            courses = account.get_courses(
                enrollment_term_id=term_id,
                state=["available"]
            )
        else:
            courses = account.get_courses(state=["available"])

        return list(courses)

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
