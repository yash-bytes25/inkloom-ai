import os
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header
import jwt

from .supabase_client import is_supabase_configured, get_supabase_client

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """Return True if running in production environment."""
    return os.environ.get("ENVIRONMENT", "development").strip().lower() == "production"


def verify_jwt_token(token: str, client: Optional[Any] = None) -> Dict[str, Any]:
    """Verify Supabase JWT token integrity, expiration, signature, and claims.

    Enforces:
    - Rejects missing, non-string, or malformed tokens.
    - Validates expiration ('exp' claim).
    - Validates cryptographic signature via SUPABASE_JWT_SECRET if present.
    - Validates via Supabase Auth API (get_user) when Supabase is configured.
    - Disallows unverified tokens in production.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=401,
            detail="Authentication credentials were not provided."
        )

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=401,
            detail="Malformed authentication token: invalid JWT format."
        )

    # 1. Header & Algorithm inspection: strictly permit only HS256 (standard Supabase JWT)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Malformed authentication token: unreadable header."
        )

    alg = unverified_header.get("alg")
    if alg == "none":
        raise HTTPException(
            status_code=401,
            detail="Invalid token algorithm: 'none' is strictly forbidden."
        )
    if alg not in ["HS256", "ES256"]:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token algorithm: '{alg}' is not permitted. Only 'HS256' and 'ES256' are supported."
        )

    # 2. Cryptographic signature and claim verification via SUPABASE_JWT_SECRET (for HS256 tokens)
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if alg == "HS256" and jwt_secret:
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={
                    "verify_exp": True,
                    "verify_signature": True,
                    "require": ["exp", "sub", "aud"],
                },
            )
            user_id = payload.get("sub")
            if not user_id or not str(user_id).strip():
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication token: missing subject (sub)."
                )

            # Validate issuer if SUPABASE_URL is configured
            supabase_url = os.environ.get("SUPABASE_URL", "").strip()
            if supabase_url and not supabase_url.startswith("https://your-project"):
                expected_iss = f"{supabase_url.rstrip('/')}/auth/v1"
                token_iss = payload.get("iss")
                if token_iss and token_iss != expected_iss:
                    raise HTTPException(
                        status_code=401,
                        detail=f"Invalid token issuer: expected '{expected_iss}', got '{token_iss}'."
                    )

            return {
                "user_id": str(user_id),
                "email": payload.get("email", ""),
                "claims": payload,
                "is_verified": True,
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired.")
        except jwt.InvalidSignatureError:
            raise HTTPException(status_code=401, detail="Invalid token signature.")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="Invalid token audience: requires 'authenticated'.")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Malformed authentication token.")
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid authentication token: {exc}")

    # 3. Supabase Auth API verification via get_user (GoTrue)
    active_client = client or (get_supabase_client(user_token=token) if is_supabase_configured() else None)
    if active_client and hasattr(active_client, "auth") and hasattr(active_client.auth, "get_user"):
        try:
            user_res = active_client.auth.get_user(token)
            if not user_res or not getattr(user_res, "user", None):
                raise HTTPException(status_code=401, detail="Invalid authentication token: user not found.")
            return {
                "user_id": str(user_res.user.id),
                "email": getattr(user_res.user, "email", "") or "",
                "is_verified": True,
            }
        except HTTPException:
            raise
        except Exception as exc:
            err_str = str(exc).lower()
            if "expired" in err_str:
                raise HTTPException(status_code=401, detail="Token has expired.")
            if "signature" in err_str:
                raise HTTPException(status_code=401, detail="Invalid token signature.")
            if "malformed" in err_str or "format" in err_str:
                raise HTTPException(status_code=401, detail="Malformed authentication token.")
            raise HTTPException(status_code=401, detail=f"Invalid authentication token: {exc}")

    # 4. If neither secret nor client verification authority is configured, reject!
    # Never accept an unverified token signature in ANY environment.
    raise HTTPException(
        status_code=401,
        detail="Unable to verify token: No verification authority (SUPABASE_JWT_SECRET or Supabase Auth) is configured."
    )


async def get_auth_context(
    authorization: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Dependency that resolves authenticated user identity and organisation context.

    Security Guarantees:
    - Never trusts browser-supplied identity claims or role headers (X-User-Role is ignored).
    - Requires verified Bearer token in production or persistent Supabase mode.
    - Derives authenticated user ID strictly from verified token.
    - Preserves local demo mode only in development when credentials are unset.
    """
    token: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None

    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format. Expected 'Bearer <token>'."
            )
        token = authorization.replace("Bearer ", "").strip()
        verified = verify_jwt_token(token)
        user_id = verified["user_id"]
        user_name = verified.get("email") or "Authenticated User"
    else:
        # No authorization header provided
        if is_production():
            raise HTTPException(
                status_code=401,
                detail="Authentication credentials were not provided. Missing Authorization Bearer token."
            )
        if is_supabase_configured():
            raise HTTPException(
                status_code=401,
                detail="Authentication credentials were not provided. Missing Authorization Bearer token."
            )
        # In-memory local demo mode (development only)
        return {
            "token": None,
            "user_id": "demo-local-user",
            "user_name": "Jordan Lee (Demo)",
            "user_role": "reviewer",
            "org_id": x_org_id or "demo-org",
            "is_demo": True,
        }

    return {
        "token": token,
        "user_id": user_id,
        "user_name": user_name,
        "user_role": None,  # Role MUST be verified from organisation_members, never client-supplied
        "org_id": x_org_id,
        "is_demo": False,
    }
