import streamlit as st
import os
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor
from utils.streaming_export import stream_to_csv
from utils.rate_limiter import global_rate_limiter


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")
st.title("Canvas Admin Rubric Extractor")

# ---------------------------------------------------
# Session State
# ---------------------------------------------------

if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False

# ---------------------------------------------------
# Core Inputs
# ---------------------------------------------------

base_url = st.text_input("Canvas Base URL")
api_key = st.text_input("Paste Admin API Token (Used Once)", type="password")
account_id = st.number_input("Account ID", value=1)

st.warning(
    """
    ⚠️ Pulling rubric data for an entire root account (Account ID 1) is NOT recommended.
    This will attempt to extract rubric data from every course and subaccount.
    It is strongly recommended to limit extraction by Enrollment Term ID.
    """
)

pull_type = st.selectbox(
    "Pull Courses By",
    ["Entire Account", "Term"],
    index=0
)

max_workers = st.slider("Parallel Workers", 2, 20, 10)

term_id = None
if pull_type == "Term":
    term_id = st.number_input("Enter Enrollment Term ID", min_value=1)

require_confirmation = account_id == 1 and pull_type == "Entire Account"
if require_confirmation:
    confirm_root = st.checkbox(
        "I understand this will extract rubric data from EVERY course in the ROOT account."
    )
else:
    confirm_root = True

# ---------------------------------------------------
# Cancellation Button
# ---------------------------------------------------

if st.button("Cancel Extraction"):
    st.session_state.cancel_requested = True

# ---------------------------------------------------
# Preview Eligible Courses
# ---------------------------------------------------

if base_url and api_key:
    if st.button("Preview Eligible Course Count"):
        canvas_client = CanvasClient(base_url, api_key)
        course_service = CourseService(canvas_client)

        with st.spinner("Estimating..."):
            courses = course_service.get_courses(
                account_id=account_id,
                pull_type=pull_type,
                term_id=term_id
            )
            courses = course_service.filter_courses(courses)

        count = len(courses)

        st.info(f"Estimated Eligible Courses: {count}")

        est_minutes = round((count * 2.5) / 60, 2)
        st.info(f"Estimated Execution Time: ~{est_minutes} minutes")

# ---------------------------------------------------
# Run Extraction
# ---------------------------------------------------

if st.button("Run Extraction"):

    if not base_url or not api_key:
        st.error("Base URL and API Token required.")
        st.stop()

    if pull_type == "Term" and not term_id:
        st.error("Term ID required.")
        st.stop()

    if not confirm_root:
        st.error("Root account confirmation required.")
        st.stop()

    st.session_state.cancel_requested = False

    canvas_client = CanvasClient(base_url, api_key)
    course_service = CourseService(canvas_client)
    rubric_service = RubricService()

    with st.spinner("Retrieving courses..."):
        courses = course_service.get_courses(
            account_id=account_id,
            pull_type=pull_type,
            term_id=term_id
        )
        courses = course_service.filter_courses(courses)

    if not courses:
        st.warning("No eligible courses found.")
        st.stop()

    st.success(f"{len(courses)} eligible courses.")

    progress = st.progress(0)
    rate_display = st.empty()
    total = len(courses)
    failed_courses = []

    start_time = time.time()

    def record_generator():
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    lambda c=c: list(RubricProcessor.generate_records(c, rubric_service))
                ): c for c in courses
            }

            for future in as_completed(futures):

                if st.session_state.cancel_requested:
                    st.warning("Extraction cancelled.")
                    break

                course = futures[future]

                try:
                    records = future.result()
                    for record in records:
                        yield record
                except Exception as e:
                    failed_courses.append({
                        "course_id": course.id,
                        "course_name": course.name,
                        "error": str(e)
                    })

                completed += 1
                progress.progress(completed / total)

                # Real-time API rate monitor
                rate_display.info(
                    f"API Rate Limit: {round(1/global_rate_limiter.interval,2)} calls/sec"
                )

    if not st.session_state.cancel_requested:
        with st.spinner("Streaming export..."):
            csv_path = stream_to_csv(record_generator())

        runtime = round((time.time() - start_time) / 60, 2)
        st.success(f"Export Complete (Runtime: {runtime} minutes)")

        with open(csv_path, "rb") as f:
            st.download_button(
                "Download CSV",
                f,
                file_name="canvas_admin_rubrics.csv",
                mime="text/csv"
            )

        os.remove(csv_path)

    # ---------------------------------------------------
    # Failed Course Log Download
    # ---------------------------------------------------

    if failed_courses:
        df_fail = pd.DataFrame(failed_courses)

        with st.expander("⚠️ Failed Courses Log"):
            st.dataframe(df_fail)

            csv_fail = df_fail.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Error Log",
                csv_fail,
                file_name="canvas_admin_rubric_errors.csv",
                mime="text/csv"
            )

    api_key = None
