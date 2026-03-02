# Canvas Admin Rubric Extractor

Enterprise-grade Streamlit application for extracting rubric assessment data across a Canvas LMS account using an Administrator API token.

This tool allows Canvas administrators to pull rubric scoring data across:

- A single Subaccount
- A single Enrollment Term
- An entire Canvas Account

The application is production hardened, containerized, rate-limited, and memory-safe for large institutional datasets.

---

## 🚀 Features

### Administrative Scope
- Pull courses by:
  - Subaccount
  - Enrollment Term (auto-discovered)
  - Entire Account
- No instructor role verification required
- Designed for Canvas Admin API tokens

### Performance & Scale
- Parallel processing (configurable worker count)
- Thread-safe rate limiting
- Exponential backoff retry logic
- Memory-safe streaming CSV export
- Designed for 1000+ course environments

### Course Filtering
Automatically skips:
- Unpublished courses
- Courses with no assignments
- Assignments without rubrics
- Submissions without graded rubric assessments

### Security & Hardening
- Canvas token pasted per run (never stored)
- Non-root Docker container
- Read-only filesystem
- No new privileges
- Resource limits enforced
- Healthcheck enabled
- No token persistence to disk

---

## 📁 Project Structure
```
canvas-admin-rubric/
│
├── app.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── services/
│   ├── canvas_client.py
│   ├── course_service.py
│   ├── rubric_service.py
│
├── processors/
│   └── rubric_processor.py
│
└── utils/
├── rate_limiter.py
├── retry.py
├── streaming_export.py
```
---

## 🐳 Deployment (Docker)

### 1️⃣ Build the Container

```bash
docker compose build
````

### 2️⃣ Start the Application

```bash
docker compose up -d
```

### 3️⃣ Access the App

```
http://your-server-ip:8501
```

---

## 🔐 Security Model

### Canvas API Token Handling

* Token is pasted into the Streamlit UI
* Token is used in memory only
* Token is not written to disk
* Token is not cached
* Token is cleared after run

### Container Hardening

* Non-root user
* Read-only filesystem
* `no-new-privileges`
* Resource limits (CPU & memory)
* Temporary files stored in tmpfs
* Healthcheck enabled

---

## ⚙️ Usage

1. Enter your Canvas base URL
   Example:
   `https://school.instructure.com`

2. Paste your Canvas Admin API token

3. Enter Account ID (typically `1`)

4. Choose course scope:

   * Subaccount
   * Term
   * Entire Account

5. Select term or subaccount (auto-discovered)

6. Adjust parallel worker count if needed

7. Click **Run Extraction**

8. Download the generated CSV

---

## 📊 Output Format

The CSV contains:

| Column          | Description         |
| --------------- | ------------------- |
| course_id       | Canvas course ID    |
| course_name     | Course name         |
| assignment_id   | Assignment ID       |
| assignment_name | Assignment name     |
| student_id      | Canvas user ID      |
| criterion_id    | Rubric criterion ID |
| score           | Points awarded      |
| comments        | Rubric comments     |

---

## 🧠 Performance Guidance

Recommended parallel workers:

| Environment Size | Workers |
| ---------------- | ------- |
| < 200 courses    | 5–8     |
| 200–1000 courses | 8–15    |
| 1000+ courses    | 15–20   |

Rate limiting is enabled at 8 API calls per second to avoid Canvas throttling.

---

## 🏫 Designed For

* District-wide rubric audits
* University-level rubric analysis
* Department benchmarking
* Accreditation documentation
* Compliance reporting
* Rubric consistency analysis

---

## 🔄 Rate Limiting & Retry

This application includes:

* Global thread-safe rate limiter
* Exponential backoff retry (max 5 attempts)
* Automatic handling of transient API errors

---

## 🛡 Recommended Production Practices

* Run behind reverse proxy (Nginx or Traefik)
* Restrict IP access via firewall
* Rotate Canvas admin tokens quarterly
* Monitor container resource usage
* Use HTTPS in production

---

## 🧪 Local Development (Without Docker)

Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

## ⚠️ Important Notes

* This tool requires a Canvas Admin API token.
* Ensure your token has permission to:

  * View courses
  * View assignments
  * View submissions
  * View rubric assessments
* Large environments may take time depending on dataset size.

---

## 📈 Scalability

Tested design supports:

* 100 courses — very fast
* 1,000 courses — stable
* 5,000+ courses — safe via streaming export

For larger institutional deployments, consider:

* Redis queue architecture
* Database persistence layer
* Async API client
* Kubernetes scaling

---

## 📜 License

Internal administrative tool.
Review institutional data policies before deployment.

---

## 🤝 Contributing

Improvements welcome:

* Rubric analytics dashboard
* Department-level grouping
* Instructor comparison
* Rubric alignment reporting
* Database export mode
