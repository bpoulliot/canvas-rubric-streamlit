import streamlit as st
import pandas as pd
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor
import plotly.express as px


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")

page = st.sidebar.radio("Navigation", ["Extraction", "Visualizations"])

# ============================================================
# Session State Initialization
# ============================================================

DEFAULT_STATE = {
    "connected": False,
    "canvas_client": None,
    "accounts": []
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# Utility: Validate Extraction Configuration
# ============================================================

def validate_configuration(pull_type, account_id, term_id):
    """
    Centralized validation guardrail.
    Prevents future ordering regressions.
    """

    if pull_type == "Term":
        return account_id is not None and account_id != 1
    else:
        return term_id is not None


# ============================================================
# Extraction Logic
# ============================================================

def run_extraction(course_service, rubric_service,
                   account_id, pull_type, term_id,
                   include_comments, max_workers):

    with st.spinner("Retrieving courses..."):
        courses = course_service.get_courses(
            account_id=account_id,
            pull_type=pull_type,
            term_id=term_id
        )

    total_courses = len(courses)

    if total_courses == 0:
        st.warning("No eligible courses found.")
        return None

    progress_bar = st.progress(0)
    status_text = st.empty()

    records = []
    completed = 0

    with st.spinner("Pulling rubrics and submissions..."):

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    lambda c=c: list(
                        RubricProcessor.generate_records(
                            c,
                            rubric_service,
                            include_comments=include_comments
                        )
                    )
                ): c for c in courses
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    records.extend(result)

                completed += 1
                progress_bar.progress(completed / total_courses)
                status_text.text(
                    f"Processed {completed} of {total_courses} courses"
                )

    return pd.DataFrame(records)


# ============================================================
# EXTRACTION PAGE
# ============================================================

if page == "Extraction":

    st.title("Canvas Admin Rubric Extractor")

    # ========================================================
    # CONNECTION VIEW
    # ========================================================

    if not st.session_state.connected:

        base_url = st.text_input("Canvas Base URL")
        api_key = st.text_input("Paste Admin API Token", type="password")

        if st.button("Connect to Canvas"):

            if not base_url or not api_key:
                st.error("Base URL and API Token required.")
            else:
                try:
                    canvas_client = CanvasClient(base_url, api_key)
                    canvas_client.get_account(1)

                    course_service = CourseService(canvas_client)
                    accounts = course_service.get_all_accounts()

                    st.session_state.canvas_client = canvas_client
                    st.session_state.accounts = accounts
                    st.session_state.connected = True

                    st.rerun()

                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")

    # ========================================================
    # EXTRACTION VIEW
    # ========================================================

    else:

        canvas_client = st.session_state.canvas_client
        course_service = CourseService(canvas_client)

        # Disconnect guardrail
        col1, col2 = st.columns([8, 2])
        with col2:
            if st.button("Disconnect"):
                for key in DEFAULT_STATE:
                    st.session_state[key] = DEFAULT_STATE[key]
                st.rerun()

        # ----------------------------------------------------
        # Input Controls (Defined FIRST)
        # ----------------------------------------------------

        pull_type = st.selectbox(
            "Pull Courses By",
            ["Term", "Entire Account"]
        )

        account_dict = {
            f"{a.name} (ID: {a.id})": a.id
            for a in st.session_state.accounts
        }

        selected_account_label = st.selectbox(
            "Select Account or Subaccount",
            list(account_dict.keys())
        )

        selected_account_id = account_dict[selected_account_label]

        terms = course_service.get_root_terms()

        EXCLUDED_TERM_NAMES = [
            "permanent term",
            "default term",
            "sandboxes for faculty",
            "summer 2017 pilot courses",
            "qm reviews"
        ]

        filtered_terms = [
            t for t in terms
            if t.name.lower() not in EXCLUDED_TERM_NAMES
        ]

        def sis_sort_key(term):
            sis_id = getattr(term, "sis_term_id", None)
            if sis_id and str(sis_id).isdigit():
                return (0, -int(sis_id))
            return (1, str(sis_id))

        filtered_terms.sort(key=sis_sort_key)

        term_dict = {
            f"{t.name} (SIS ID: {getattr(t,'sis_term_id',None)})": t.id
            for t in filtered_terms
        }

        selected_term_label = st.selectbox(
            "Select Enrollment Term",
            list(term_dict.keys())
        )

        selected_term_id = term_dict[selected_term_label]

        # ----------------------------------------------------
        # Validation (AFTER inputs defined)
        # ----------------------------------------------------

        valid_configuration = validate_configuration(
            pull_type,
            selected_account_id,
            selected_term_id
        )

        if pull_type == "Term" and selected_account_id == 1:
            st.warning(
                "Pull by Term requires selecting an account other than root (ID = 1)."
            )

        if pull_type == "Entire Account" and not selected_term_id:
            st.warning(
                "Pull by Entire Account requires selecting an Enrollment Term."
            )

        include_comments = False

        if pull_type == "Term":
            include_comments = st.toggle(
                "Pull Rubric Comments",
                value=False
            )

        max_workers = st.slider("Parallel Workers", 2, 20, 10)

        # ----------------------------------------------------
        # Run Extraction
        # ----------------------------------------------------

        if not valid_configuration:
            st.warning("Complete required selections before running extraction.")

        if st.button("Run Extraction", disabled=not valid_configuration):

            rubric_service = RubricService()

            df = run_extraction(
                course_service,
                rubric_service,
                selected_account_id,
                pull_type,
                selected_term_id,
                include_comments,
                max_workers
            )

            if df is not None and not df.empty:

                st.session_state["rubric_df"] = df

                st.success("Extraction complete.")

                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    file_name="canvas_admin_rubrics.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Extraction completed but no rubric data was found.")


# ============================================================
# VISUALIZATIONS PAGE
# ============================================================

if page == "Visualizations":

    st.title("Rubric Analytics Dashboard")

    if "rubric_df" not in st.session_state:
        st.info("Run an extraction first.")
    else:

        df = st.session_state["rubric_df"]

        if df.empty:
            st.warning("No rubric data available.")
        else:

            tab1, tab2 = st.tabs(["Heatmap", "Raw Data"])

            with tab1:
                heatmap_data = (
                    df.groupby(["course_name", "criterion_name"])["score"]
                    .mean()
                    .reset_index()
                )

                pivot = heatmap_data.pivot(
                    index="course_name",
                    columns="criterion_name",
                    values="score"
                )

                fig = px.imshow(pivot, text_auto=True, aspect="auto")
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.dataframe(df)
