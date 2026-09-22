# Canvas Admin Rubric Extractor

Enterprise-grade Streamlit application for extracting, analyzing, and reporting on Canvas LMS rubric assessment data at scale.

This tool is designed for Canvas administrators and institutional research teams who require:

* Governed account scoping
* Root-level term enforcement
* FERPA-compliant exports
* Comment scrubbing
* Advanced visual analytics
* Executive PDF reporting

---

# 🚀 Core Capabilities

## Extraction Modes

### Pull Courses By:

* **Entire Account**
* **Enrollment Term**

---

## 🔐 Governance & Safety Controls

### Root-Only Term Enforcement

When "Pull Courses By = Term":

* Enrollment terms are loaded **only from the root account (ID = 1)**
* Subaccount term loading is disabled
* Prevents term scope ambiguity

---

### Enrollment Term Filtering

The following terms are automatically excluded from the dropdown:

* Permanent term
* Default Term
* Sandboxes for faculty
* Summer 2017 pilot courses
* QM Reviews

Filtering is case-insensitive.

---

### Term Ordering Logic

Terms are sorted by:

1. Descending numerical SIS ID (most recent first)
2. Non-numeric SIS IDs appear last

Dropdown display format:

```
Term Name (SIS ID: XXXXX)
```

---

### Account Filtering

Accounts are excluded if their name contains (case-insensitive):

* blueprint
* @uccs.edu
* canvas demo courses
* self-enroll
* committees
* templates
* zoom testing
* manually
* permanent
* special
* no announcements

---

### Account Ordering Logic

Accounts are ordered using the following grouping:

1. Accounts containing `_college`
2. All other accounts
3. Accounts containing `archive`

Within each group: alphabetical (case-insensitive)

---

# 🧾 Rubric Data Extraction

Extracted fields include:

| Column                | Description                    |
| --------------------- | ------------------------------ |
| course_name           | Canvas course name             |
| assignment_name       | Assignment name                |
| rubric_name           | Rubric title                   |
| criterion_name        | Criterion display name         |
| criterion_description | Detailed criterion description |
| score                 | Points awarded                 |
| rubric_comment        | Scrubbed comment (if enabled)  |

---

## 🔒 FERPA Compliance

The export will **never include**:

* student_id
* user_id
* student_name
* criterion_id

---

# 💬 Optional Rubric Comment Extraction

Toggle: **Pull Rubric Comments**

### OFF

* No comments retrieved

### ON

* Retrieves all rubric comments
* Automatically scrubs:

  * Student first names
  * Student last names
* Case-insensitive whole-word replacement
* Replaces detected names with:

```
[REDACTED]
```

---

# 📊 Visualization Dashboard

Navigate to **Visualizations** in the sidebar.

---

## 🔥 Heatmap

* Criterion × Course average score heatmap
* Quickly identify strengths and weaknesses
* Color-coded performance

---

## 📈 Statistical Variance Analysis

Includes:

* Mean
* Median
* Standard Deviation
* Variance
* Coefficient of Variation
* Boxplot distribution

---

## 🏆 Benchmarking Dashboard

Provides:

* Global average score
* Course-level comparison
* Ranked performance table
* Visual course vs global comparison chart

---

## 🧠 Filtering Controls

* Filter by course
* Filter by term (if present)
* Dynamic updates across all visualizations

---

# 📄 Exportable PDF Report Builder

From the Visualizations page:

Generate a structured executive report including:

* Title page
* Timestamp
* Global statistics
* Course benchmarking table
* Clean formatted layout

Exported as:

```
canvas_rubric_report.pdf
```

---

# ⚡ Performance & Scaling

## Parallel Processing

* Configurable worker count (2–20)
* ThreadPoolExecutor-based

## Dynamic Runtime Estimation

During extraction:

Displays:

* % complete
* Elapsed time
* ETA remaining
* Estimated completion clock

Estimates dynamically adjust based on actual course processing time.

---

## Streaming-Safe Architecture

* Handles large institutional datasets
* Avoids loading unnecessary objects into memory
* Safe for 1000+ course environments

---

# 🐳 Docker Deployment

## Build

```bash
docker compose build
```

## Run

```bash
docker compose up -d
```

Access at:

```
http://<server-ip>:8501
```

---

# 🔐 Security Model

* API token pasted per run
* Token never stored
* Token cleared after execution
* Non-root container
* Read-only filesystem
* No new privileges
* Resource limits enforced
* Healthcheck enabled

---

# 📈 Recommended Usage

For institutional environments:

* Prefer "Term" extraction over full account
* Use SIS ID ordering to select most recent term
* Avoid root-level full extraction unless necessary
* Use comment toggle only when required

---

# 📦 Example Use Cases

* Accreditation audits
* Rubric consistency analysis
* Department benchmarking
* Institutional quality review
* Criterion variance analysis
* Faculty development insights
* Program-level reporting

---

# 🧠 Architecture Overview

* Streamlit frontend
* CanvasAPI backend integration
* Root-scoped term governance
* Structured account filtering
* Privacy-safe comment scrubbing
* Plotly analytics engine
* ReportLab PDF reporting

---

# ⚠️ Operational Notes

* Large term extractions may take significant time
* Parallel workers increase speed but also increase API load
* Ensure API token has:

  * Account-level permissions
  * Rubric visibility
  * Enrollment term access

---

# 🔮 Future Enhancement Roadmap

Potential enhancements include:

* Instructor-level benchmarking
* Criterion-level benchmarking across departments
* Z-score normalization
* Longitudinal term comparison
* Outlier detection engine
* Confidence interval analysis
* NLP-based comment clustering
* Institutional branding in PDF
* Automated scheduled reporting
* Kubernetes deployment support

---

# 🏫 Designed For

* Universities
* Community colleges
* Multi-campus systems
* Statewide systems
* Institutional research teams
* Academic affairs offices

---

# License

Internal administrative tool.
Ensure compliance with institutional data governance policies before deployment.
