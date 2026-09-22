from utils.retry import retry
from utils.rate_limiter import global_rate_limiter


class RubricService:

    @retry()
    def get_assignments_with_rubrics(self, course):
        """
        Returns assignments that have rubrics attached.
        """

        global_rate_limiter.wait()

        assignments = list(course.get_assignments())

        rubric_assignments = []

        for assignment in assignments:
            rubric = getattr(assignment, "rubric", None)
            if rubric:
                rubric_assignments.append(assignment)

        return rubric_assignments

    @retry()
    def get_submission_rubric_data(self, assignment):
        """
        Retrieves submissions including rubric assessments.
        """

        global_rate_limiter.wait()

        submissions = assignment.get_submissions(
            include=["rubric_assessment"]
        )

        valid_submissions = []

        for submission in submissions:

            rubric_assessment = getattr(
                submission,
                "rubric_assessment",
                None
            )

            if rubric_assessment:
                valid_submissions.append(submission)

        return valid_submissions
