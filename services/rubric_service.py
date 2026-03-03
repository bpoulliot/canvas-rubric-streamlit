from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class RubricService:

    @retry()
    def get_course_rubrics(self, course):
        """
        Uses /api/v1/courses/:course_id/rubrics
        """

        global_rate_limiter.wait()

        rubrics = course.get_rubrics(
            include=[
                "assessments",
                "assignment_associations",
                "course_associations"
            ],
            style="full"
        )

        return list(rubrics)
