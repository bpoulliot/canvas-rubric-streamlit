import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor
import plotly.express as px


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

    else:

        canvas_client = st.session_state.canvas_client
        course_service = CourseService(canvas_client)

        col1, col2 = st.columns([8, 2])
        with col2:
            if st.button("Disconnect"):
                st.session_state.connected = False
                st.session_state.canvas_client = None
                st.session_state.accounts = []
                st.rerun()

        pull_type = st.selectbox("Pull Courses By", ["Term", "Entire Account"])

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

        term_dict = {
            f"{t.name} (SIS ID: {getattr(t,'sis_term_id',None)})": t.id
            for t in filtered_terms
        }

        selected_term_label = st.selectbox(
            "Select Enrollment Term",
            list(term_dict.keys())
        )

        selected_term_id = term_dict[selected_term_label]

        include_comments = False

        if pull_type == "Term":
            if selected_account_id == 1:
                st.warning("Pull by Term requires selecting an account other than root.")
            else:
                include_comments = st.toggle("Pull Rubric Comments", value=False)

        max_workers = st.slider("Parallel Workers", 2, 20, 10)

        if st.button("Run Extraction"):

            rubric_service = RubricService()

            courses = course_service.get_courses(
                account_id=selected_account_id,
                pull_type=pull_type,
                term_id=selected_term_id
            )

            records = []

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
        st.info("Run an extraction first.")
    else:

        df = st.session_state["rubric_df"]

        if df.empty:
            st.warning("No rubric data available.")
        else:

            fig = px.histogram(df, x="score", nbins=20)
            st.plotly_chart(fig, use_container_width=True)

            pivot = (
                df.groupby(["course_name", "criterion_name"])["score"]
                .mean()
                .reset_index()
                .pivot(index="course_name", columns="criterion_name", values="score")
            )

            fig2 = px.imshow(pivot, text_auto=True, aspect="auto")
            st.plotly_chart(fig2, use_container_width=True)
