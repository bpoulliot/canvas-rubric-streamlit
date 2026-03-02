import streamlit as st
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.canvas_client import CanvasClient
from services.course_service import CourseService
from services.rubric_service import RubricService
from processors.rubric_processor import RubricProcessor
from utils.streaming_export import stream_to_csv


st.set_page_config(page_title="Canvas Admin Rubric Extractor", layout="wide")
st.title("Canvas Admin Rubric Extractor")

base_url = st.text_input("Canvas Base URL (e.g. https://school.instructure.com)")
api_key = st.text_input("Paste Admin API Token (Used Once)", type="password")
account_id = st.number_input("Account ID", value=1)

pull_type = st.selectbox(
    "Pull Courses By",
    ["Subaccount", "Term", "Entire Account"]
)

max_workers = st.slider("Parallel Workers", 2, 20, 10)

if st.button("Run Extraction"):

    if not base_url or not api_key:
        st.error("Base URL and Token required.")
        st.stop()

    canvas_client = CanvasClient(base_url, api_key)
    course_service = CourseService(canvas_client)
    rubric_service = RubricService()

    if pull_type == "Term":
        terms = course_service.get_terms(account_id)
        term_map = {t.name: t.id for t in terms}
        selected = st.selectbox("Select Term", list(term_map.keys()))
        term_id = term_map[selected]
        subaccount_id = None
    elif pull_type == "Subaccount":
        subs = course_service.get_subaccounts(account_id)
        sub_map = {s.name: s.id for s in subs}
        selected = st.selectbox("Select Subaccount", list(sub_map.keys()))
        subaccount_id = sub_map[selected]
        term_id = None
    else:
        term_id = None
        subaccount_id = None

    with st.spinner("Retrieving courses..."):
        courses = course_service.get_courses(
            account_id,
            pull_type,
            subaccount_id=subaccount_id,
            term_id=term_id
        )
        courses = course_service.filter_courses(courses)

    st.success(f"{len(courses)} eligible courses.")

    progress = st.progress(0)
    total = len(courses)

    def record_generator():
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(
                lambda c=c: RubricProcessor.generate_records(c, rubric_service)
            ): c for c in courses}

            for future in as_completed(futures):
                generator = future.result()
                if generator:
                    for record in generator:
                        yield record

                completed += 1
                progress.progress(completed / total)

    with st.spinner("Streaming export..."):
        csv_path = stream_to_csv(record_generator())

    st.success("Export Complete")

    with open(csv_path, "rb") as f:
        st.download_button(
            "Download CSV",
            f,
            file_name="canvas_admin_rubrics.csv",
            mime="text/csv"
        )

    os.remove(csv_path)

    # Immediately delete token reference
    api_key = None
