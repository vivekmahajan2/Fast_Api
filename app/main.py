from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import jobs, candidates
from app.core.database import supabase
from app.core.config import settings

app = FastAPI(
    title="AI Career Agent Backend",
    version="1.0.0",
    description="FastAPI backend connected to Supabase for automated job ingestion, LangGraph matching, and human-in-the-loop application approval."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(jobs.router)
app.include_router(candidates.router)

@app.get("/")
def root():
    return {
        "service": "AI Career Agent Backend",
        "database": "Supabase (PostgreSQL)",
        "llm_engine": f"Groq ({settings.GROQ_MODEL})" if settings.GROQ_API_KEY else "Heuristic Fallback (set GROQ_API_KEY)",
        "status": "online",
        "docs_url": "/docs"
    }

@app.get("/health/supabase")
def check_supabase():
    """Verify active connectivity to Supabase."""
    if not supabase:
        return {
            "status": "pending_configuration",
            "database": "Supabase (fallback to in-memory store)",
            "connected": False,
            "message": "SUPABASE_URL and SUPABASE_KEY are not configured in .env. Running in local fallback mode."
        }
    try:
        res = supabase.table("candidate_profiles").select("count", count="exact").limit(0).execute()
        return {
            "status": "healthy",
            "database": "Supabase",
            "connected": True,
            "supabase_url": settings.SUPABASE_URL
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "Supabase",
            "connected": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
