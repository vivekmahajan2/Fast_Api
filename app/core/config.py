from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_ENV: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Supabase credentials
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""  # Recommend using service_role key for backend service
    
    # Job provider
    RAPIDAPI_KEY: Optional[str] = None
    JOB_PROVIDER: str = "jsearch"
    
    # LLM keys
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
