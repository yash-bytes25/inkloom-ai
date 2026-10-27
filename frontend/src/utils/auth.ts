/**
 * Authentication and Session Management Utility for Inkloom AI
 * ============================================================
 * Provides secure handling of Supabase Auth tokens, session restoration,
 * expiration verification, and Bearer token header injection.
 */

export interface AuthUser {
  id: string
  email: string
}

export interface AuthSession {
  access_token: string
  refresh_token?: string | null
  expires_at?: number | null
  user: AuthUser
  org_id?: string
  role?: string
  is_demo: boolean
}

export const AUTH_STORAGE_KEY = 'inkloom_ai_auth_session'

/**
 * Retrieve active session from localStorage with expiration verification.
 */
export function getStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null

    const session: AuthSession = JSON.parse(raw)
    if (!session || !session.access_token || !session.user) {
      clearSession()
      return null
    }

    // Check expiration if expires_at is present (seconds unix epoch)
    if (session.expires_at) {
      const nowSeconds = Math.floor(Date.now() / 1000)
      if (session.expires_at <= nowSeconds) {
        clearSession()
        return null
      }
    }

    return session
  } catch {
    clearSession()
    return null
  }
}

/**
 * Persist authenticated session into localStorage.
 */
export function saveSession(session: AuthSession): void {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
  } catch {
    // LocalStorage quota or access error handled gracefully
  }
}

/**
 * Remove session from localStorage upon logout or session invalidation.
 */
export function clearSession(): void {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY)
  } catch {
    // Ignore error
  }
}

/**
 * Build Authorization headers containing Bearer token and optional tenant org id.
 */
export function getAuthHeaders(session: AuthSession | null): Record<string, string> {
  if (!session || !session.access_token) {
    return {}
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  }

  if (session.org_id) {
    headers['X-Org-Id'] = session.org_id
  }

  return headers
}
