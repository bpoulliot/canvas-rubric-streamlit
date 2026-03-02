import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")

page = st.sidebar.radio("Navigation", ["Extraction", "Visualizations"])

# ---------------------------------------------------
# Session State Initialization
# ---------------------------------------------------

if "connected" not in st.session_state:
    st.session_state.connected = False

if "accounts" not in st.session_state:
    st.session_state.accounts = []

if "canvas_client" not in st.session_state:
    st.session_state.canvas_client = None


# ===================================================
# EXTRACTION PAGE
# ===================================================

if page == "Extraction":

    st.title("Canvas Admin Rubric Extractor")

    base_url = st.text_input("Canvas Base URL")
    api_key = st.text_input("Paste Admin API Token", type="password")

    # ---------------------------------------------------
    # CONNECTION STEP
    # ---------------------------------------------------

    if not st.session_state.connected:

        if st.button("Connect to Canvas"):

            if not base_url or not api_key:
                st.error("Base URL and API Token required.")
                st.stop()

            try:
                with st.spinner("Validating connection..."):

                    canvas_client = CanvasClient(base_url, api_key)

                    # Validate root account access
                    root_account = canvas_client.get_account(1)

                st.success("Connection validated.")

                # Async load accounts
                with st.spinner("Loading accounts..."):

                    course_service = CourseService(canvas_client)

                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            course_service.get_all_accounts
                        )
                        accounts = future.result()

                st.session_state.canvas_client = canvas_client
                st.session_state.accounts = accounts
                st.session_state.connected = True

                st.success("Accounts loaded successfully.")

            except Exception as e:
                st.error(f"Connection failed: {str(e)}")
                st.stop()

        st.stop()

    # ---------------------------------------------------
    # POST-CONNECTION UI
    # ---------------------------------------------------

    canvas_client = st.session_state.canvas_client
    course_service = CourseService(canvas_client)

    account_dict = {
        f"{a.name} (ID: {a.id})": a.id
        for a in st.session_state.accounts
    }

    selected_account_label = st.selectbox(
        "Select Account or Subaccount",
        list(account_dict.keys())
    )

    selected_account_id = account_dict[selected_account_label]

    pull_type = st.selectbox(
        "Pull Courses By",
        ["Entire Account", "Term"],
        index=0
    )

    include_comments = st.toggle("Pull Rubric Comments", value=False)
    max_workers = st.slider("Parallel Workers", 2, 20, 10)

    selected_term_id = None

    if pull_type == "Term":

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

        # Estimated courses checkbox (TERM ONLY)
        estimate_courses = st.checkbox("Estimate Eligible Courses")

        if estimate_courses:

            with st.spinner("Estimating eligible courses..."):

                preview_courses = course_service.get_courses(
                    account_id=selected_account_id,
                    pull_type="Term",
                    term_id=selected_term_id
                )

                preview_courses = course_service.filter_courses(preview_courses)

                course_count = len(preview_courses)

                estimated_seconds = int(course_count * 2.5)
                estimated_time = str(timedelta(seconds=estimated_seconds))

            st.info(
                f"{course_count} courses selected which is estimated to take "
                f"{estimated_time} to complete."
            )

    # ---------------------------------------------------
    # RUN EXTRACTION
    # ---------------------------------------------------

    if st.button("Run Extraction"):

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

                for future in futures:
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

    if "rubric_df" not in st.session_state:
        st.warning("No rubric data available. Run Extraction first.")
        st.stop()

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

        fig = px.imshow(
            pivot,
            text_auto=True,
            aspect="auto",
            title="Average Score Heatmap"
        )

        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)
