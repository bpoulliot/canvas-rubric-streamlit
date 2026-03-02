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

for key in [
    "cancel_requested",
    "terms_loaded",
    "accounts_loaded",
    "terms_dict",
    "accounts_dict"
]:
    if key not in st.session_state:
        st.session_state[key] = False if "loaded" in key or "cancel" in key else {}

# ---------------------------------------------------
# Core Inputs
# ---------------------------------------------------

base_url = st.text_input("Canvas Base URL")
api_key = st.text_input("Paste Admin API Token (Used Once)", type="password")

pull_type = st.selectbox(
    "Pull Courses By",
    ["Entire Account", "Term"],
    index=0
)

max_workers = st.slider("Parallel Workers", 2, 20, 10)

selected_account_id = None
selected_term_id = None

# ---------------------------------------------------
# Entire Account Mode: Auto-load Accounts
# ---------------------------------------------------

if pull_type == "Entire Account":

    if base_url and api_key and not st.session_state.accounts_loaded:

        try:
            canvas_client = CanvasClient(base_url, api_key)
            course_service = CourseService(canvas_client)

            with st.spinner("Loading accounts and subaccounts..."):
                accounts = course_service.get_all_accounts()

            if not accounts:
                st.error("No accessible accounts found for this API token.")
                st.stop()

            st.session_state.accounts_dict = {
                f"{a.name} (ID: {a.id})": a.id for a in accounts
            }

            st.session_state.accounts_loaded = True

        except Exception as e:
            st.error(f"Failed to load accounts: {str(e)}")
            st.stop()

    if st.session_state.accounts_loaded:
        selected_account_label = st.selectbox(
            "Select Account or Subaccount",
            list(st.session_state.accounts_dict.keys())
        )
        selected_account_id = st.session_state.accounts_dict[selected_account_label]

# ---------------------------------------------------
# Term Mode: Load Terms Under Selected Root Account
# ---------------------------------------------------

if pull_type == "Term":

    if base_url and api_key and not st.session_state.accounts_loaded:

        try:
            canvas_client = CanvasClient(base_url, api_key)
            course_service = CourseService(canvas_client)

            with st.spinner("Loading accessible accounts..."):
                accounts = course_service.get_all_accounts()

            st.session_state.accounts_dict = {
                f"{a.name} (ID: {a.id})": a.id for a in accounts
            }

            st.session_state.accounts_loaded = True

        except Exception as e:
            st.error(str(e))
            st.stop()

    if st.session_state.accounts_loaded:
        selected_account_label = st.selectbox(
            "Select Account",
            list(st.session_state.accounts_dict.keys())
        )
        selected_account_id = st.session_state.accounts_dict[selected_account_label]

    if selected_account_id and not st.session_state.terms_loaded:
        try:
            canvas_client = CanvasClient(base_url, api_key)
            course_service = CourseService(canvas_client)

            with st.spinner("Loading enrollment terms..."):
                terms = course_service.get_terms(selected_account_id)

            st.session_state.terms_dict = {
                f"{t.name} (ID: {t.id})": t.id for t in terms
            }

            st.session_state.terms_loaded = True

        except Exception as e:
            st.error(str(e))
            st.stop()

    if st.session_state.terms_loaded:
        selected_term_label = st.selectbox(
            "Select Enrollment Term",
            list(st.session_state.terms_dict.keys())
        )
        selected_term_id = st.session_state.terms_dict[selected_term_label]

# ---------------------------------------------------
# Cancellation Button
# ---------------------------------------------------

if st.button("Cancel Extraction"):
    st.session_state.cancel_requested = True

# ---------------------------------------------------
# Run Extraction
# ---------------------------------------------------

if st.button("Run Extraction"):

    if not base_url or not api_key:
        st.error("Base URL and API Token required.")
        st.stop()

    if not selected_account_id:
        st.error("Please select an Account.")
        st.stop()

    if pull_type == "Term" and not selected_term_id:
        st.error("Please select an Enrollment Term.")
        st.stop()

    st.session_state.cancel_requested = False

    canvas_client = CanvasClient(base_url, api_key)
    course_service = CourseService(canvas_client)
    rubric_service = RubricService()

    try:
        with st.spinner("Retrieving courses..."):
            courses = course_service.get_courses(
                account_id=selected_account_id,
                pull_type=pull_type,
                term_id=selected_term_id
            )
            courses = course_service.filter_courses(courses)

    except Exception as e:
        st.error(str(e))
        st.stop()

    if not courses:
        st.warning("No eligible courses found.")
        st.stop()

    st.success(f"{len(courses)} eligible courses.")

    progress = st.progress(0)
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
