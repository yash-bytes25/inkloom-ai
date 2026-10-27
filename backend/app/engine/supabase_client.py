import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

PLACEHOLDER_URL = "https://your-project-ref.supabase.co"
PLACEHOLDER_KEY = "your_supabase_anon_key_here"
PLACEHOLDER_SERVICE_KEY = "your_supabase_service_role_key_here"


def is_supabase_configured() -> bool:
    """Check if valid Supabase credentials are provided in the environment.
    Returns False when credentials are unset, empty, or placeholders.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip() or os.environ.get("SUPABASE_KEY", "").strip()

    if not url or url == PLACEHOLDER_URL:
        return False
    if not key or key in [PLACEHOLDER_KEY, "your_supabase_anon_or_service_key_here"]:
        return False

    return True


def get_supabase_client(user_token: Optional[str] = None, use_service_role: bool = False) -> Optional[Client]:
    """Initialize a Supabase Client.

    Args:
        user_token: Optional JWT token of the authenticated user to enforce RLS via auth.uid().
        use_service_role: If True, uses SUPABASE_SERVICE_ROLE_KEY for server-side administrative tasks.
                         NEVER expose service role keys to clients.
    """
    if not is_supabase_configured():
        return None

    url = os.environ.get("SUPABASE_URL", "").strip()

    if use_service_role:
        service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not service_key or service_key == PLACEHOLDER_SERVICE_KEY:
            logger.warning("SUPABASE_SERVICE_ROLE_KEY requested but not configured.")
            return None
        key_to_use = service_key
    else:
        key_to_use = os.environ.get("SUPABASE_ANON_KEY", "").strip() or os.environ.get("SUPABASE_KEY", "").strip()

    try:
        client: Client = create_client(url, key_to_use)

        # If an authenticated user token is provided, attach it for RLS scoping
        if user_token:
            client.postgrest.auth(user_token)

        return client
    except Exception as exc:
        logger.warning(f"Failed to initialize Supabase client: {exc}")
        return None
