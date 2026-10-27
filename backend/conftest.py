import os
import sys
from pathlib import Path
import pytest

# Add project root to sys.path so 'backend.app' is importable in all environments
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def isolate_unit_test_environment(request, monkeypatch):
    """Isolate offline unit tests from live Supabase configuration.

    When running unit test modules (everything except test_live_supabase_integration),
    mask Supabase environment variables so the application reliably runs in fast,
    deterministic local demo mode without network dependencies.
    """
    is_live_test = "test_live_supabase_integration" in request.node.fspath.basename
    if not is_live_test:
        for var in [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_JWT_SECRET",
        ]:
            if var in os.environ:
                monkeypatch.delenv(var, raising=False)

