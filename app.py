import streamlit as st
import pandas as pd
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")

page = st.sidebar.radio("Navigation", ["Extraction", "Visualizations"])

# ---------------------------------------------------
# Session State
# ---------------------------------------------------

if "connected" not in st.session_state:
    st.session_state.connected = False

if "canvas_client" not in st.session_state:
    st.session_state.canvas_client = None

if "accounts" not in st.session_state:
    st.session_state.accounts = []

if "connection_timestamp" not in st.session_state:
    st.session_state.connection_timestamp = None


# ===================================================
# EXTRACTION PAGE
# ===================================================

if page == "Extraction":

    st.title("Canvas Admin Rubric Extractor")

    base_url = st.text_input("Canvas Base URL")
    api_key = st.text_input("Paste Admin API Token", type="password")

    # ---------------------------------------------------
    # CONNECTION
    # ---------------------------------------------------

    if not st.session_state.connected:

        if st.button("Connect to Canvas"):

            if base_url and api_key:
                try:
                    with st.spinner("Validating connection..."):
                        canvas_client = CanvasClient(base_url, api_key)
                        canvas_client.get_account(1)

                    course_service = CourseService(canvas_client)

                    with st.spinner("Loading accounts..."):
                        accounts = course_service.get_all_accounts()

                    st.session_state.canvas_client = canvas_client
                    st.session_state.accounts = accounts
                    st.session_state.connected = True
                    st.session_state.connection_timestamp = time.time()

                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")
            else:
                st.error("Base URL and API Token required.")

    # ---------------------------------------------------
    # POST CONNECTION UI
    # ---------------------------------------------------

    if st.session_state.connected:

        if st.session_state.connection_timestamp:
            if time.time() - st.session_state.connection_timestamp < 3:
                st.success("Connected successfully.")
            else:
                st.session_state.connection_timestamp = None

        canvas_client = st.session_state.canvas_client
        course_service = CourseService(canvas_client)

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

        # ---------------------------------------------------
        # TERMS
        # ---------------------------------------------------

        with st.spinner("Loading root enrollment terms..."):
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

        # ---------------------------------------------------
        # VALIDATION + WARNINGS
        # ---------------------------------------------------

        valid_configuration = False

        if pull_type == "Term":

            if selected_account_id == 1:
                st.warning(
                    "Pull by Term requires selecting an account other than the root account (ID = 1)."
                )
            else:
                valid_configuration = True

            include_comments = st.toggle("Pull Rubric Comments", value=False)

        else:
            include_comments = False

            if not selected_term_id:
                st.warning(
                    "Pull by Entire Account requires selecting an Enrollment Term."
                )
            else:
                valid_configuration = True

        # ---------------------------------------------------
        # ESTIMATE COURSES (WITH PROGRESS)
        # ---------------------------------------------------

        if valid_configuration:

            estimate_courses = st.checkbox("Estimate Eligible Courses")

            if estimate_courses:

                with st.spinner("Estimating eligible courses..."):

                    preview_courses = course_service.get_courses(
                        account_id=selected_account_id,
                        pull_type=pull_type,
                        term_id=selected_term_id
                    )

                    progress_bar = st.progress(0)

                    filtered_preview = []
                    total_preview = len(preview_courses)

                    for i, course in enumerate(preview_courses):
                        filtered_preview.extend(
                            course_service.filter_courses([course])
                        )
                        progress_bar.progress((i + 1) / total_preview)

                    course_count = len(filtered_preview)

                    estimated_seconds = int(course_count * 2.5)
                    estimated_time = str(timedelta(seconds=estimated_seconds))

                st.info(
                    f"{course_count} courses selected which is estimated to take "
                    f"{estimated_time} to complete."
                )

        # ---------------------------------------------------
        # RUN EXTRACTION
        # ---------------------------------------------------

        max_workers = st.slider("Parallel Workers", 2, 20, 10)

        extraction_ready = (
            base_url
            and api_key
            and valid_configuration
        )

        if not extraction_ready:
            st.warning("Please complete required selections before running extraction.")

        if st.button("Run Extraction", disabled=not extraction_ready):

            rubric_service = RubricService()

            with st.spinner("Retrieving courses..."):

                courses = course_service.get_courses(
                    account_id=selected_account_id,
                    pull_type=pull_type,
                    term_id=selected_term_id
                )

                courses = course_service.filter_courses(courses)

            st.info(f"{len(courses)} eligible courses found.")

            records = []

            with st.spinner("Processing courses..."):

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

            df = pd.DataFrame(records)

            for col in ["student_id", "student_name", "criterion_id"]:
                if col in df.columns:
                    df.drop(columns=[col], inplace=True)

            st.session_state["rubric_df"] = df

            st.success("Extraction complete.")

            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="canvas_admin_rubrics.csv",
                mime="text/csv"
            )


# ===================================================
# VISUALIZATIONS PAGE
# ===================================================

if page == "Visualizations":

    st.title("Rubric Visualizations")

    if "rubric_df" in st.session_state:

        df = st.session_state["rubric_df"]

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

            st.dataframe(pivot)

        with tab2:
            st.dataframe(df)

    else:
        st.info("Run an extraction first to see visualizations.")
