from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class RubricService:

    @retry()
    def get_assignments_with_rubrics(self, course):
        global_rate_limiter.wait()
        assignments = list(course.get_assignments())
        return [a for a in assignments if getattr(a, "rubric", None)]

    @retry()
    def get_active_submissions(self, assignment):
        global_rate_limiter.wait()
        submissions = assignment.get_submissions(
            include=["rubric_assessment"]
        )

        return [
            s for s in submissions
            if s.workflow_state == "graded" and s.rubric_assessment
        ]
