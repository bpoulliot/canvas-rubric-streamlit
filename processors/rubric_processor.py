import re


class RubricProcessor:

    @staticmethod
    def scrub_names(comment, student_names):
        if not comment:
            return comment

        for name in student_names:
            pattern = r"\b" + re.escape(name) + r"\b"
            comment = re.sub(pattern, "[REDACTED]", comment, flags=re.IGNORECASE)

        return comment

    @staticmethod
    def generate_records(course, rubric_service, include_comments=False):

        assignments = rubric_service.get_assignments_with_rubrics(course)

        if not assignments:
            return

        # Build student name list for scrubbing
        student_names = []
        if include_comments:
            enrollments = course.get_enrollments(type=["StudentEnrollment"])
            for e in enrollments:
                if hasattr(e, "user") and e.user:
                    name_parts = e.user["name"].split()
                    student_names.extend(name_parts)

        for assignment in assignments:

            rubric_name = assignment.name  # Canvas does not always expose rubric title directly

            # Build rubric criterion lookup from assignment.rubric
            rubric_criteria_lookup = {}
            if hasattr(assignment, "rubric") and assignment.rubric:
                for criterion in assignment.rubric:
                    rubric_criteria_lookup[criterion["id"]] = {
                        "criterion_name": criterion.get("description"),
                        "criterion_description": criterion.get("long_description")
                    }

            submissions = rubric_service.get_active_submissions(assignment)

            if not submissions:
                continue

            for submission in submissions:

                rubric_data = submission.rubric_assessment

                for cid, cdata in rubric_data.items():

                    criterion_meta = rubric_criteria_lookup.get(cid, {})

                    comment = None
                    if include_comments:
                        comment = cdata.get("comments")
                        comment = RubricProcessor.scrub_names(
                            comment,
                            student_names
                        )

                    yield {
                        "course_name": course.name,
                        "assignment_name": assignment.name,
                        "rubric_name": rubric_name,
                        "criterion_name": criterion_meta.get("criterion_name"),
                        "criterion_description": criterion_meta.get("criterion_description"),
                        "score": cdata.get("points"),
                        "rubric_comment": comment if include_comments else None
                    }
