import streamlit as st
import pandas as pd
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

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

if "canvas_client" not in st.session_state:
    st.session_state.canvas_client = None

if "accounts" not in st.session_state:
    st.session_state.accounts = []


# ===================================================
# EXTRACTION PAGE
# ===================================================

if page == "Extraction":

    st.title("Canvas Admin Rubric Extractor")

    # ===================================================
    # CONNECTION VIEW
    # ===================================================

    if not st.session_state.connected:

        base_url = st.text_input("Canvas Base URL")
        api_key = st.text_input("Paste Admin API Token", type="password")

        if st.button("Connect to Canvas"):

            if not base_url or not api_key:
                st.error("Base URL and API Token required.")
            else:
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

                    # Critical: force clean rerun into extraction view
                    st.rerun()

                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")

    # ===================================================
    # EXTRACTION VIEW
    # ===================================================

    else:

        canvas_client = st.session_state.canvas_client
        course_service = CourseService(canvas_client)

        # Disconnect Button
        col1, col2 = st.columns([8, 2])
        with col2:
            if st.button("Disconnect"):
                st.session_state.connected = False
                st.session_state.canvas_client = None
                st.session_state.accounts = []
                st.rerun()

        # ---------------------------------------------------
        # Pull Mode
        # ---------------------------------------------------

        pull_type = st.selectbox(
            "Pull Courses By",
            ["Term", "Entire Account"]
        )

        # ---------------------------------------------------
        # Account Dropdown
        # ---------------------------------------------------

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
        # Enrollment Term Dropdown (Root Only)
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
        # Validation Rules
        # ---------------------------------------------------

        valid_configuration = False

        if pull_type == "Term":

            if selected_account_id == 1:
                st.warning(
                    "Pull by Term requires selecting an account other than root (ID = 1)."
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
        # Estimate Toggle (runs after click)
        # ---------------------------------------------------

        estimate_toggle = st.toggle("Estimate Eligible Courses", value=False)

        max_workers = st.slider("Parallel Workers", 2, 20, 10)

        extraction_ready = valid_configuration

        if not extraction_ready:
            st.warning("Complete required selections before running extraction.")

        # ---------------------------------------------------
        # Run Extraction
        # ---------------------------------------------------

        if st.button("Run Extraction", disabled=not extraction_ready):

            # -----------------------------------------------
            # Fast Estimation (after click)
            # -----------------------------------------------

            if estimate_toggle:

                with st.spinner("Estimating eligible courses..."):

                    course_count = course_service.count_courses(
                        account_id=selected_account_id,
                        pull_type=pull_type,
                        term_id=selected_term_id
                    )

                    estimated_seconds = int(course_count * 2.5)
                    estimated_time = str(timedelta(seconds=estimated_seconds))

                st.info(
                    f"{course_count} courses selected which is estimated to take "
                    f"{estimated_time} to complete."
                )

            # -----------------------------------------------
            # Actual Extraction
            # -----------------------------------------------

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

    st.title("Rubric Analytics Dashboard")

    if "rubric_df" not in st.session_state:
        st.info("Run an extraction first to view analytics.")
    else:

        df = st.session_state["rubric_df"].copy()

        # ==================================================
        # SIDEBAR FILTERING
        # ==================================================

        st.sidebar.header("Filters")

        if "course_name" in df.columns:
            selected_courses = st.sidebar.multiselect(
                "Filter by Course",
                sorted(df["course_name"].unique()),
                default=list(df["course_name"].unique())
            )
            df = df[df["course_name"].isin(selected_courses)]

        if "rubric_name" in df.columns:
            selected_rubrics = st.sidebar.multiselect(
                "Filter by Rubric",
                sorted(df["rubric_name"].dropna().unique()),
                default=list(df["rubric_name"].dropna().unique())
            )
            df = df[df["rubric_name"].isin(selected_rubrics)]

        if df.empty:
            st.warning("No data available after filtering.")
            st.stop()

        # ==================================================
        # KPI METRICS
        # ==================================================

        total_courses = df["course_name"].nunique()
        total_records = len(df)
        global_mean = df["score"].mean()
        global_std = df["score"].std()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Courses Included", total_courses)
        col2.metric("Rubric Records", total_records)
        col3.metric("Global Mean Score", round(global_mean, 2))
        col4.metric("Score Std Dev", round(global_std, 2))

        st.divider()

        # ==================================================
        # TABS
        # ==================================================

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Score Distribution",
            "Criterion Analysis",
            "Course Benchmarking",
            "Heatmap",
            "Comments Insights"
        ])

        # ==================================================
        # 1️⃣ SCORE DISTRIBUTION
        # ==================================================

        with tab1:

            st.subheader("Score Distribution")

            fig = px.histogram(
                df,
                x="score",
                nbins=20,
                title="Distribution of Rubric Scores"
            )

            st.plotly_chart(fig, use_container_width=True)

            fig_box = px.box(
                df,
                y="score",
                title="Score Variability (Boxplot)"
            )

            st.plotly_chart(fig_box, use_container_width=True)

        # ==================================================
        # 2️⃣ CRITERION ANALYSIS
        # ==================================================

        with tab2:

            st.subheader("Average Score by Criterion")

            criterion_avg = (
                df.groupby("criterion_name")["score"]
                .mean()
                .reset_index()
                .sort_values("score", ascending=False)
            )

            fig = px.bar(
                criterion_avg,
                x="criterion_name",
                y="score",
                title="Average Score per Criterion"
            )

            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Criterion Variability")

            criterion_std = (
                df.groupby("criterion_name")["score"]
                .std()
                .reset_index()
                .sort_values("score", ascending=False)
            )

            fig_std = px.bar(
                criterion_std,
                x="criterion_name",
                y="score",
                title="Standard Deviation per Criterion"
            )

            st.plotly_chart(fig_std, use_container_width=True)

        # ==================================================
        # 3️⃣ COURSE BENCHMARKING
        # ==================================================

        with tab3:

            st.subheader("Course Benchmarking vs Global Mean")

            course_avg = (
                df.groupby("course_name")["score"]
                .mean()
                .reset_index()
            )

            course_avg["Difference from Mean"] = (
                course_avg["score"] - global_mean
            )

            course_avg = course_avg.sort_values("score", ascending=False)

            fig = px.bar(
                course_avg,
                x="course_name",
                y="score",
                color="Difference from Mean",
                color_continuous_scale="RdYlGn",
                title="Course Average vs Institutional Mean"
            )

            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(course_avg, use_container_width=True)

        # ==================================================
        # 4️⃣ HEATMAP
        # ==================================================

        with tab4:

            st.subheader("Course × Criterion Heatmap")

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

        # ==================================================
        # 5️⃣ COMMENTS INSIGHTS
        # ==================================================

        with tab5:

            if "rubric_comment" in df.columns and df["rubric_comment"].notna().any():

                st.subheader("Comment Volume")

                df_comments = df[df["rubric_comment"].notna()].copy()
                df_comments["comment_length"] = df_comments["rubric_comment"].str.len()

                fig = px.histogram(
                    df_comments,
                    x="comment_length",
                    nbins=30,
                    title="Distribution of Comment Length"
                )

                st.plotly_chart(fig, use_container_width=True)

                comment_counts = (
                    df_comments.groupby("criterion_name")
                    .size()
                    .reset_index(name="comment_count")
                )

                fig_counts = px.bar(
                    comment_counts,
                    x="criterion_name",
                    y="comment_count",
                    title="Comments by Criterion"
                )

                st.plotly_chart(fig_counts, use_container_width=True)

            else:
                st.info("No rubric comments available in dataset.")
