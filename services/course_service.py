from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class CourseService:

    def __init__(self, canvas_client):
        self.client = canvas_client

    @retry()
    def get_courses(self, account_id, pull_type, term_id=None):
        """
        Pull courses strictly by:
        - Entire Account (account_id only)
        - Account ID AND Term ID (if Term selected)
        """

        global_rate_limiter.wait()
        account = self.client.get_account(account_id)

        if pull_type == "Term":
            if not term_id:
                raise ValueError("Term ID must be provided when pull_type='Term'")

            # Explicit: account scoped + term scoped
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

    def filter_courses(self, courses):
        """
        Skip:
        - Unpublished courses
        - Courses with no assignments
        """

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
