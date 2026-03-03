class RubricProcessor:

    @staticmethod
    def generate_records(course, rubric_service, include_comments=False):

        rubrics = rubric_service.get_course_rubrics(course)

        # Ignore courses without rubrics
        if not rubrics:
            return

        for rubric in rubrics:

            rubric_title = getattr(rubric, "title", None)

            criteria_lookup = {}

            rubric_data = getattr(rubric, "data", {})

            for criterion in rubric_data.get("criteria", []):
                criteria_lookup[criterion["id"]] = {
                    "criterion_name": criterion.get("description"),
                    "criterion_description": criterion.get("long_description")
                }

            assessments = rubric_data.get("assessments", [])

            for assessment in assessments:

                assessment_data = assessment.get("data", {})

                for criterion_id, criterion_result in assessment_data.items():

                    criterion_meta = criteria_lookup.get(criterion_id, {})

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
