import streamlit as st
import os
import time
import pandas as pd
import plotly.express as px
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")

page = st.sidebar.radio(
    "Navigation",
    ["Extraction", "Visualizations"]
)

# ===================================================
# EXTRACTION PAGE
# ===================================================

if page == "Extraction":

    st.title("Canvas Admin Rubric Extractor")

    base_url = st.text_input("Canvas Base URL")
    api_key = st.text_input("Paste Admin API Token (Used Once)", type="password")

    pull_type = st.selectbox(
        "Pull Courses By",
        ["Entire Account", "Term"],
        index=0
    )

    include_comments = st.toggle(
        "Pull Rubric Comments",
        value=False
    )

    max_workers = st.slider("Parallel Workers", 2, 20, 10)

    selected_account_id = None
    selected_term_id = None

    if base_url and api_key:

        canvas_client = CanvasClient(base_url, api_key)
        course_service = CourseService(canvas_client)

        # ---------------------------------------------------
        # Load Accounts (Filtered + Ordered)
        # ---------------------------------------------------

        accounts = course_service.get_all_accounts()

        account_dict = {
            f"{a.name} (ID: {a.id})": a.id for a in accounts
        }

        selected_account_label = st.selectbox(
            "Select Account or Subaccount",
            list(account_dict.keys())
        )

        selected_account_id = account_dict[selected_account_label]

        # ---------------------------------------------------
        # Load Terms FROM ROOT ACCOUNT ONLY
        # ---------------------------------------------------

        if pull_type == "Term":

            terms = course_service.get_root_terms()

            term_dict = {}

            for t in terms:
                sis_id = getattr(t, "sis_term_id", None)
                label = f"{t.name} (SIS ID: {sis_id})"
                term_dict[label] = t.id

            selected_term_label = st.selectbox(
                "Select Enrollment Term",
                sorted(term_dict.keys())
            )

            selected_term_id = term_dict[selected_term_label]

    # ---------------------------------------------------
    # Run Extraction
    # ---------------------------------------------------

    if st.button("Run Extraction"):

        rubric_service = RubricService()

        courses = course_service.get_courses(
            account_id=selected_account_id,
            pull_type=pull_type,
            term_id=selected_term_id
        )

        courses = course_service.filter_courses(courses)

        st.info(f"{len(courses)} eligible courses found.")

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

        for col in ["student_id", "student_name", "criterion_id"]:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        st.session_state["rubric_df"] = df

        st.success("Extraction complete")

        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="canvas_admin_rubrics.csv",
            mime="text/csv"
        )
