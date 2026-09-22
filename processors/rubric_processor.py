class RubricProcessor:

    @staticmethod
    def generate_records(course, rubric_service, include_comments=False):

        assignments = rubric_service.get_assignments_with_rubrics(course)

        if not assignments:
            return

        for assignment in assignments:

            rubric_metadata = getattr(assignment, "rubric", None)

            if not rubric_metadata:
                continue

            rubric_title = getattr(assignment, "name", None)

            # Build criteria lookup from assignment.rubric
            criteria_lookup = {}

            for criterion in rubric_metadata:
                criteria_lookup[criterion.get("id")] = {
                    "criterion_name": criterion.get("description"),
                    "criterion_description": criterion.get("long_description")
                }

            submissions = rubric_service.get_submission_rubric_data(assignment)

            if not submissions:
                continue

            for submission in submissions:

                rubric_assessment = getattr(
                    submission,
                    "rubric_assessment",
                    None
                )

                if not rubric_assessment:
                    continue

                for criterion_id, criterion_result in rubric_assessment.items():

                    criterion_meta = criteria_lookup.get(
                        criterion_id,
                        {}
                    )

                    comment = (
                        criterion_result.get("comments")
                        if include_comments
                        else None
                    )

                    yield {
                        "course_name": course.name,
                        "rubric_name": rubric_title,
                        "criterion_name": criterion_meta.get("criterion_name"),
                        "criterion_description": criterion_meta.get("criterion_description"),
                        "score": criterion_result.get("points"),
                        "rubric_comment": comment
                    }
