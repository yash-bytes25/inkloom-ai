import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert'
import {
  getStoredSession,
  saveSession,
  clearSession,
  getAuthHeaders,
  AUTH_STORAGE_KEY,
  type AuthSession,
} from './auth.ts'

// Polyfill minimal localStorage for Node test runner
const memoryStore = new Map<string, string>()
globalThis.localStorage = {
  getItem: (key: string) => memoryStore.get(key) ?? null,
  setItem: (key: string, value: string) => {
    memoryStore.set(key, value)
  },
  removeItem: (key: string) => {
    memoryStore.delete(key)
  },
  clear: () => {
    memoryStore.clear()
  },
  key: (index: number) => Array.from(memoryStore.keys())[index] ?? null,
  length: 0,
} as unknown as Storage

describe('Frontend Authentication and Session Management', () => {
  beforeEach(() => {
    memoryStore.clear()
  })

  it('saves and restores active session correctly', () => {
    const validSession: AuthSession = {
      access_token: 'test-jwt-token-123',
      user: { id: 'usr-1', email: 'creator@novasound.example' },
      is_demo: false,
      org_id: 'org-test',
      role: 'creator',
    }

    saveSession(validSession)
    const restored = getStoredSession()

    assert.notStrictEqual(restored, null)
    assert.strictEqual(restored?.access_token, 'test-jwt-token-123')
    assert.strictEqual(restored?.user.email, 'creator@novasound.example')
    assert.strictEqual(restored?.role, 'creator')
  })

  it('detects and clears expired session', () => {
    const pastTimestamp = Math.floor(Date.now() / 1000) - 300 // 5 minutes ago
    const expiredSession: AuthSession = {
      access_token: 'expired-jwt',
      expires_at: pastTimestamp,
      user: { id: 'usr-expired', email: 'expired@novasound.example' },
      is_demo: false,
    }

    saveSession(expiredSession)
    const restored = getStoredSession()

    assert.strictEqual(restored, null)
    assert.strictEqual(memoryStore.has(AUTH_STORAGE_KEY), false)
  })

  it('clears session on explicit logout', () => {
    const session: AuthSession = {
      access_token: 'token-to-clear',
      user: { id: 'usr-2', email: 'reviewer@novasound.example' },
      is_demo: false,
    }

    saveSession(session)
    assert.strictEqual(memoryStore.has(AUTH_STORAGE_KEY), true)

    clearSession()
    assert.strictEqual(getStoredSession(), null)
  })

  it('generates proper Authorization and X-Org-Id headers', () => {
    assert.deepStrictEqual(getAuthHeaders(null), {})

    const sessionWithOrg: AuthSession = {
      access_token: 'jwt-header-token',
      user: { id: 'usr-3', email: 'admin@novasound.example' },
      is_demo: false,
      org_id: 'org-novasound',
    }

    const headers = getAuthHeaders(sessionWithOrg)
    assert.strictEqual(headers.Authorization, 'Bearer jwt-header-token')
    assert.strictEqual(headers['X-Org-Id'], 'org-novasound')
  })
})
