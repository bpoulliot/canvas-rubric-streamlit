import streamlit as st
import os
import time
import pandas as pd
import plotly.express as px
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor
from utils.streaming_export import stream_to_csv


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

    max_workers = st.slider("Parallel Workers", 2, 20, 10)

    selected_account_id = None
    selected_term_id = None

    if base_url and api_key:

        canvas_client = CanvasClient(base_url, api_key)
        course_service = CourseService(canvas_client)

        accounts = course_service.get_all_accounts()

        account_dict = {
            f"{a.name} (ID: {a.id})": a.id for a in accounts
        }

        selected_account_label = st.selectbox(
            "Select Account or Subaccount",
            list(account_dict.keys())
        )

        selected_account_id = account_dict[selected_account_label]

        if pull_type == "Term":

            terms = course_service.get_terms(selected_account_id)

            term_dict = {
                f"{t.name} (ID: {t.id})": t.id for t in terms
            }

            selected_term_label = st.selectbox(
                "Select Enrollment Term",
                list(term_dict.keys())
            )

            selected_term_id = term_dict[selected_term_label]

    if st.button("Run Extraction"):

        rubric_service = RubricService()

        courses = course_service.get_courses(
            account_id=selected_account_id,
            pull_type=pull_type,
            term_id=selected_term_id
        )

        courses = course_service.filter_courses(courses)

        total = len(courses)
        st.info(f"{total} eligible courses found.")

        records = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    lambda c=c: list(RubricProcessor.generate_records(c, rubric_service))
                ): c for c in courses
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    records.extend(result)

        df = pd.DataFrame(records)
        
        # Ensure no student identifiers are ever present
        for col in ["student_id", "user_id", "student_name", "criterion_id"]:
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

# ===================================================
# VISUALIZATION PAGE
# ===================================================

if page == "Visualizations":

    st.title("Rubric Visualizations")

    if "rubric_df" not in st.session_state:
        st.warning("No rubric data available. Run Extraction first.")
        st.stop()

    df = st.session_state["rubric_df"]

    tab1, tab2, tab3 = st.tabs([
        "Heatmap",
        "Benchmarking",
        "PDF Report"
    ])

    # ------------------------------------------------
    # HEATMAP
    # ------------------------------------------------

    with tab1:
        heatmap_data = (
            df.groupby(["course_name", "criterion_id"])["score"]
            .mean()
            .reset_index()
        )

        pivot = heatmap_data.pivot(
            index="course_name",
            columns="criterion_id",
            values="score"
        )

        fig = px.imshow(
            pivot,
            text_auto=True,
            aspect="auto",
            title="Average Score Heatmap"
        )

        st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------
    # BENCHMARKING
    # ------------------------------------------------

    with tab2:
        global_average = df["score"].mean()

        course_avg = (
            df.groupby("course_name")["score"]
            .mean()
            .reset_index()
            .sort_values("score", ascending=False)
        )

        st.metric("Global Average Score", round(global_average, 2))

        fig = px.bar(
            course_avg,
            x="course_name",
            y="score",
            title="Course Average vs Global Average"
        )

        st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------
    # PDF REPORT BUILDER
    # ------------------------------------------------

    with tab3:

        st.subheader("Generate Executive PDF Report")

        if st.button("Generate PDF Report"):

            pdf_path = "rubric_report.pdf"
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            elements = []

            styles = getSampleStyleSheet()
            title_style = styles["Heading1"]
            normal_style = styles["Normal"]

            elements.append(Paragraph("Canvas Rubric Analytics Report", title_style))
            elements.append(Spacer(1, 0.3 * inch))

            elements.append(
                Paragraph(
                    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    normal_style
                )
            )

            elements.append(Spacer(1, 0.3 * inch))

            # Global Stats
            mean_score = df["score"].mean()
            std_dev = df["score"].std()
            variance = df["score"].var()

            elements.append(Paragraph("Global Statistics", styles["Heading2"]))
            elements.append(Spacer(1, 0.2 * inch))

            stats_data = [
                ["Metric", "Value"],
                ["Mean Score", round(mean_score, 2)],
                ["Standard Deviation", round(std_dev, 2)],
                ["Variance", round(variance, 2)],
                ["Total Records", len(df)]
            ]

            table = Table(stats_data, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black)
            ]))

            elements.append(table)
            elements.append(Spacer(1, 0.4 * inch))

            # Benchmark Table
            elements.append(Paragraph("Course Benchmarking", styles["Heading2"]))
            elements.append(Spacer(1, 0.2 * inch))

            course_avg = (
                df.groupby("course_name")["score"]
                .mean()
                .reset_index()
                .sort_values("score", ascending=False)
            )

            benchmark_data = [["Course", "Average Score"]]

            for _, row in course_avg.iterrows():
                benchmark_data.append([
                    row["course_name"],
                    round(row["score"], 2)
                ])

            table2 = Table(benchmark_data, hAlign="LEFT")
            table2.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black)
            ]))

            elements.append(table2)

            doc.build(elements)

            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download PDF Report",
                    f,
                    file_name="canvas_rubric_report.pdf",
                    mime="application/pdf"
                )

            os.remove(pdf_path)
