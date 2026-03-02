from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class RubricService:

    @retry()
    def get_assignments_with_rubrics(self, course):
        global_rate_limiter.wait()

        assignments = list(course.get_assignments())

        return [
            a for a in assignments
            if getattr(a, "rubric", None)
        ]

    @retry()
    def get_active_submissions(self, assignment):
        """
        Safely retrieves submissions that include rubric assessments.
        Prevents AttributeError if rubric_assessment not present.
        """

        global_rate_limiter.wait()

        submissions = assignment.get_submissions(
            include=["rubric_assessment"]
        )

        valid_submissions = []

        for s in submissions:

            # Safely check workflow_state
            workflow_state = getattr(s, "workflow_state", None)

            # Safely check rubric_assessment
            rubric_assessment = getattr(s, "rubric_assessment", None)

            if workflow_state == "graded" and rubric_assessment:
                valid_submissions.append(s)

        return valid_submissions
