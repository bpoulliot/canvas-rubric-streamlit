class RubricProcessor:

    @staticmethod
    def generate_records(course, rubric_service):

        assignments = rubric_service.get_assignments_with_rubrics(course)
        if not assignments:
            return

        for assignment in assignments:
            submissions = rubric_service.get_active_submissions(assignment)
            if not submissions:
                continue

            for submission in submissions:
                for cid, cdata in submission.rubric_assessment.items():
                    yield {
                        "course_id": course.id,
                        "course_name": course.name,
                        "assignment_id": assignment.id,
                        "assignment_name": assignment.name,
                        "student_id": submission.user_id,
                        "criterion_id": cid,
                        "score": cdata.get("points"),
                        "comments": cdata.get("comments"),
                    }
