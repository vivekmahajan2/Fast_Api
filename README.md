# AI Career Agent - Supabase & FastAPI Backend

A production-ready FastAPI backend backed by **Supabase (PostgreSQL)** for scheduling job searches via n8n, deduplicating listings, evaluating candidate matches via LangGraph, and managing human-in-the-loop approvals.

---

## 🚀 Quick Setup with Supabase (3 Steps)

### 1. Run the Database Schema in Supabase
1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Create a new project (or select an existing one).
3. In the left sidebar, click on **SQL Editor** -> **+ New Query**.
4. Open [supabase_schema.sql](file:///d:/n8n_1/supabase_schema.sql), copy its entire contents, paste it into the editor, and click **Run**.
   - This sets up the `candidate_profiles`, `jobs`, `job_matches`, and `application_approvals` tables.
   - It also creates unique indexes for automatic deduplication on `(provider, external_job_id)`.

---

### 2. Configure Environment Variables
1. In your Supabase Dashboard, go to **Project Settings** -> **API**.
2. Copy:
   - **Project URL** (`SUPABASE_URL`)
   - **service_role secret key** (`SUPABASE_KEY`) *(Recommended for backend server operations)*
3. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
4. Fill in your keys in `.env`:
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_supabase_service_role_key
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   RAPIDAPI_KEY=your_rapidapi_key_optional_for_live_jsearch
   ```

---

### 3. Install Dependencies & Run Server
```bash
# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

Once started:
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Supabase Healthcheck**: [http://localhost:8000/health/supabase](http://localhost:8000/health/supabase)

---

## 📡 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/jobs/fetch` | Ingests jobs from provider, translates filters, deduplicates in Supabase |
| `GET` | `/api/jobs` | Queries saved jobs with filters (`status`, `workplace_type`, `min_score`) |
| `GET` | `/api/jobs/{job_id}` | Retrieves full job details and LangGraph match breakdown |
| `POST` | `/api/jobs/match` | Runs candidate skill evaluation and saves scores to `job_matches` |
| `PATCH` | `/api/jobs/{job_id}/status` | Updates progression state (`shortlisted`, `applied`, `rejected`) |
| `POST` | `/api/jobs/{job_id}/approve` | Records human-in-the-loop approval before external application actions |
| `GET/POST`| `/api/candidates/profile` | Manage candidate skills, preferences, and experience in Supabase |

---

## 🔄 n8n Integration
Schedule an HTTP Request node in n8n every 6 hours targeting:
```http
POST http://localhost:8000/api/jobs/fetch
Content-Type: application/json

{
  "keywords": ["AI Engineer", "Machine Learning Engineer"],
  "country": "India",
  "workplace_type": "remote",
  "experience_level": ["internship", "entry_level"],
  "posted_within_days": 7
}
```
Followed by a check on `new_inserted_count > 0` and triggering `/api/jobs/match`.
"# Fast_Api" 
