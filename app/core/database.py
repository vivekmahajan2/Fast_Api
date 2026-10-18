from typing import Optional
from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Optional[Client]:
    """
    Initializes and returns the Supabase client using configured credentials.
    Returns None gracefully if credentials are not configured or still placeholders.
    """
    if (
        not settings.SUPABASE_URL 
        or not settings.SUPABASE_KEY 
        or "your-project" in settings.SUPABASE_URL
        or "your_supabase" in settings.SUPABASE_KEY
    ):
        return None
    
    try:
        clean_url = (
            settings.SUPABASE_URL.strip()
            .replace("/rest/v1/", "")
            .replace("/rest/v1", "")
            .rstrip("/")
        )
        return create_client(clean_url, settings.SUPABASE_KEY.strip())
    except Exception as e:
        print(f"Warning: Could not connect to Supabase: {e}")
        return None

# Singleton client instance (may be None if not yet configured)
supabase: Optional[Client] = get_supabase_client()

