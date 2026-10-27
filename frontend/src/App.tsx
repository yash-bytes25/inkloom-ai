import { useState, useEffect } from 'react'
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Info,
  ArrowRight,
  BookOpen,
  RotateCcw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  FileText,
  Wand2,
  Send,
  Check,
  X,
  MessageSquare,
  History,
  UserCheck,
  AlertCircle,
  XCircle,
  Plus,
  RefreshCw,
  Database,
  GitCompare,
} from 'lucide-react'
import type {
  Finding,
  ReviewResponse,
  BrandRulesConfig,
  Severity,
  EvidenceStatus,
  Submission,
  ReviewStatus,
  DecisionType,
} from './types/governance'
import { BrandGuidelinesEditor } from './components/BrandGuidelinesEditor'
import { RevisionDiffViewer } from './components/RevisionDiffViewer'
import {
  getStoredSession,
  saveSession,
  clearSession,
  getAuthHeaders,
  type AuthSession,
} from './utils/auth'

const API_BASE = (import.meta.env.VITE_API_URL as string) || 'http://127.0.0.1:8000'

const SAMPLE_COPY_OPTIONS = [
  {
    label: 'Sample 1: Multiple Violations',
    text: 'These cheap headphones and earbuds feature a lifetime warranty. The NovaSound Apex Wireless costs $199 and our unbreakable build kills the competition.',
  },
  {
    label: 'Sample 2: Compliant Copy',
    text: 'Experience the NovaSound Apex Wireless with our patented Active Acoustic Isolation™. At $299, it delivers 40 hours of continuous high-fidelity sound.',
  },
  {
    label: 'Sample 3: Water Spec & Disclaimer Issue',
    text: 'NovaSound Pulse Earphones are 100% waterproof and provide guaranteed hearing protection for everyday listening.',
  },
]

export function App() {
  // Submission & Workflow State
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [activeSubmission, setActiveSubmission] = useState<Submission | null>(null)
  const [content, setContent] = useState<string>('')
  const [submissionTitle, setSubmissionTitle] = useState<string>('')
  const [reviewerComment, setReviewerComment] = useState<string>('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'audit' | 'workflow' | 'diff' | 'guidelines'>('audit')
  const [showNewModal, setShowNewModal] = useState<boolean>(false)
  const [newTitle, setNewTitle] = useState<string>('')
  const [newContent, setNewContent] = useState<string>('')
  const [expandedSnapshotId, setExpandedSnapshotId] = useState<string | null>(null)
  const [includeAi, setIncludeAi] = useState<boolean>(true)

  // Authentication & Session State
  const [session, setSession] = useState<AuthSession | null>(getStoredSession())
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false)
  const [authEmail, setAuthEmail] = useState<string>('')
  const [authPassword, setAuthPassword] = useState<string>('')
  const [authLoading, setAuthLoading] = useState<boolean>(false)
  const [authError, setAuthError] = useState<string | null>(null)

  // Policy Review & System State
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null)
  const [demoRules, setDemoRules] = useState<BrandRulesConfig | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [backendOnline, setBackendOnline] = useState<boolean>(false)
  const [storageMode, setStorageMode] = useState<'supabase_persistent' | 'local_demo'>('local_demo')
  const [showRulesDrawer, setShowRulesDrawer] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Authenticated API request wrapper
  const apiFetch = async (
    endpoint: string,
    options: RequestInit = {},
    overrideSession?: AuthSession | null
  ): Promise<Response> => {
    const currentSession = overrideSession !== undefined ? overrideSession : session
    const authHeaders = getAuthHeaders(currentSession)
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...authHeaders,
      },
    })

    if (response.status === 401 && currentSession) {
      clearSession()
      setSession(null)
      setErrorMsg('Your authenticated session has expired or is invalid. Switched to local unauthenticated mode.')
    }

    return response
  }

  // Handle Authentication (Supabase Cloud password login or Local Demo Persona)
  const handleLogin = async (e?: React.FormEvent, personaEmail?: string) => {
    if (e) e.preventDefault()
    setAuthLoading(true)
    setAuthError(null)

    const emailToUse = personaEmail || authEmail.trim()
    const passwordToUse = personaEmail ? 'demo-password' : authPassword

    if (!emailToUse) {
      setAuthError('Email is required.')
      setAuthLoading(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailToUse, password: passwordToUse }),
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Authentication failed (${res.status})`)
      }

      const data: AuthSession = await res.json()
      saveSession(data)
      setSession(data)
      setShowAuthModal(false)
      setAuthEmail('')
      setAuthPassword('')
      setSuccessMsg(`Signed in as ${data.user.email}`)
      setTimeout(() => setSuccessMsg(null), 3000)
      await bootstrap(data)
    } catch (err: unknown) {
      setAuthError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    clearSession()
    setSession(null)
    setSuccessMsg('Signed out successfully.')
    setTimeout(() => setSuccessMsg(null), 3000)
    bootstrap(null)
  }

  // Standalone or combined review evaluation
  const runAudit = async (textToReview?: string, overrideAi?: boolean) => {
    const targetText = textToReview !== undefined ? textToReview : content
    const shouldRunAi = overrideAi !== undefined ? overrideAi : includeAi
    setLoading(true)
    setErrorMsg(null)

    try {
      const response = await apiFetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: targetText,
          rules: null,
          include_ai: shouldRunAi,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}: ${response.statusText}`)
      }

      const data: ReviewResponse = await response.json()
      setReviewResult(data)
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message)
      } else {
        setErrorMsg('Failed to connect to review engine')
      }
    } finally {
      setLoading(false)
    }
  }

  const refreshSubmissions = async (preferredId?: string, activeSession?: AuthSession | null) => {
    try {
      const res = await apiFetch('/api/submissions', {}, activeSession)
      if (res.ok) {
        const list: Submission[] = await res.json()
        setSubmissions(list)

        const target = preferredId
          ? list.find((s) => s.id === preferredId) || list[0]
          : activeSubmission
          ? list.find((s) => s.id === activeSubmission.id) || list[0]
          : list[0]

        if (target) {
          setActiveSubmission(target)
          setContent(target.content)
          setSubmissionTitle(target.title)
          if (target.latest_review_response) {
            setReviewResult(target.latest_review_response)
          } else {
            runAudit(target.content, false)
          }
        } else {
          setContent(SAMPLE_COPY_OPTIONS[0].text)
          runAudit(SAMPLE_COPY_OPTIONS[0].text, false)
        }
      }
    } catch {
      // Backend error
    }
  }

  const bootstrap = async (overrideSession?: AuthSession | null) => {
    const activeSession = overrideSession !== undefined ? overrideSession : session
    try {
      const healthRes = await fetch(`${API_BASE}/api/health`)
      if (healthRes.ok) {
        setBackendOnline(true)
        const healthData = await healthRes.json().catch(() => ({}))
        if (healthData.storage_mode) {
          setStorageMode(healthData.storage_mode)
        }

        // Verify active session with backend if present
        if (activeSession?.access_token) {
          try {
            const meRes = await apiFetch('/api/auth/me', {}, activeSession)
            if (meRes.ok) {
              const meData = await meRes.json()
              if (meData.role && meData.role !== activeSession.role) {
                const updatedSession = { ...activeSession, role: meData.role }
                saveSession(updatedSession)
                setSession(updatedSession)
              }
            }
          } catch {
            // Error handled in apiFetch
          }
        }

        const rulesRes = await apiFetch('/api/guidelines', {}, activeSession).catch(() =>
          fetch(`${API_BASE}/api/demo-rules`)
        )
        if (rulesRes.ok) {
          const rulesData: BrandRulesConfig = await rulesRes.json()
          setDemoRules(rulesData)
        }
        await refreshSubmissions(undefined, activeSession)
      } else {
        setBackendOnline(false)
      }
    } catch {
      setBackendOnline(false)
    }
  }

  const handleSaveGuidelines = async (updatedRules: BrandRulesConfig) => {
    setActionLoading(true)
    setErrorMsg(null)
    try {
      const res = await apiFetch('/api/guidelines', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedRules),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to update brand guidelines')
      }
      const savedData: BrandRulesConfig = await res.json()
      setDemoRules(savedData)
      setSuccessMsg(`Brand guidelines for "${savedData.brand_name}" updated successfully.`)
      setTimeout(() => setSuccessMsg(null), 4000)
      if (content) {
        runAudit(content, includeAi)
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleResetGuidelines = async () => {
    setActionLoading(true)
    setErrorMsg(null)
    try {
      const res = await apiFetch('/api/guidelines/reset', {
        method: 'POST',
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to reset brand guidelines')
      }
      const resetData: BrandRulesConfig = await res.json()
      setDemoRules(resetData)
      setSuccessMsg('Restored original NovaSound Audio demo rules.')
      setTimeout(() => setSuccessMsg(null), 4000)
      if (content) {
        runAudit(content, includeAi)
      }
    } finally {
      setActionLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    bootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelectSubmission = (sub: Submission) => {
    setActiveSubmission(sub)
    setContent(sub.content)
    setSubmissionTitle(sub.title)
    setReviewerComment('')
    setCommentError(null)
    setErrorMsg(null)
    setSuccessMsg(null)
    if (sub.latest_review_response) {
      setReviewResult(sub.latest_review_response)
    } else {
      runAudit(sub.content, false)
    }
  }

  // Save changes to active submission.
  // Note: If content changed, backend resets status to 'draft', increments version, and invalidates previous approvals.
  // Save changes to active submission.
  // Note: If content changed, backend resets status to 'draft', increments version, and invalidates previous approvals.
  const handleSaveSubmission = async () => {
    if (!activeSubmission) return
    setActionLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      const res = await apiFetch(`/api/submissions/${activeSubmission.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          title: submissionTitle || activeSubmission.title,
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Failed to update submission (${res.status})`)
      }

      const updated: Submission = await res.json()
      setActiveSubmission(updated)
      setContent(updated.content)
      setSubmissionTitle(updated.title)
      if (updated.latest_review_response) {
        setReviewResult(updated.latest_review_response)
      }

      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))

      if (updated.version > activeSubmission.version) {
        setSuccessMsg(
          `Content updated to v${updated.version}. Status reset to Draft (prior approvals invalidated as per brand policy).`
        )
      } else {
        setSuccessMsg('Submission metadata updated successfully.')
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error updating submission')
    } finally {
      setActionLoading(false)
    }
  }

  // Creator submits content for reviewer evaluation
  const handleSubmitForReview = async () => {
    if (!activeSubmission) return
    setActionLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      // If content was modified, save it first so submission is evaluated on latest copy
      if (content !== activeSubmission.content) {
        await apiFetch(`/api/submissions/${activeSubmission.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content,
            title: submissionTitle || activeSubmission.title,
          }),
        })
      }

      const creatorName = session ? session.user.email : activeSubmission.creator_name
      const res = await apiFetch(`/api/submissions/${activeSubmission.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          creator_name: creatorName,
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Failed to submit for review (${res.status})`)
      }

      const updated: Submission = await res.json()
      setActiveSubmission(updated)
      setContent(updated.content)
      if (updated.latest_review_response) {
        setReviewResult(updated.latest_review_response)
      }
      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setSuccessMsg(`Submission v${updated.version} sent for review. Status is now 'In Review'.`)
      setActiveTab('workflow')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error submitting for review')
    } finally {
      setActionLoading(false)
    }
  }

  // Trigger combined Gemini AI contextual audit on active submission
  const handleRunAiSubmissionAudit = async () => {
    if (!activeSubmission) return
    setActionLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      const res = await apiFetch(`/api/submissions/${activeSubmission.id}/ai-audit`, {
        method: 'POST',
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `AI audit failed (${res.status})`)
      }

      const updated: Submission = await res.json()
      setActiveSubmission(updated)
      if (updated.latest_review_response) {
        setReviewResult(updated.latest_review_response)
      }
      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setSuccessMsg(`Gemini AI contextual review completed on v${updated.version}.`)
      setActiveTab('audit')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error running AI audit')
    } finally {
      setActionLoading(false)
    }
  }

  // Reviewer records decision: approved, changes_requested, or rejected
  const handleRecordDecision = async (decision: DecisionType) => {
    if (!activeSubmission) return
    setCommentError(null)
    setErrorMsg(null)
    setSuccessMsg(null)

    // Enforce comment validation for rejection and change requests
    if (decision === 'changes_requested' || decision === 'rejected') {
      if (!reviewerComment || !reviewerComment.trim()) {
        const action = decision === 'changes_requested' ? 'requesting revisions' : 'rejecting copy'
        setCommentError(`A comment explaining the rationale is strictly required when ${action}.`)
        return
      }
    }

    setActionLoading(true)
    try {
      const reviewerName = session ? session.user.email : 'Alex Morgan (Demo Brand Guardian)'
      const isDemoReviewer = session ? session.is_demo : true
      const res = await apiFetch(`/api/submissions/${activeSubmission.id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          reviewer_name: reviewerName,
          is_demo_reviewer: isDemoReviewer,
          comment: reviewerComment.trim() || (decision === 'approved' ? 'Approved — certified brand compliant.' : ''),
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Failed to record decision (${res.status})`)
      }

      const updated: Submission = await res.json()
      setActiveSubmission(updated)
      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setReviewerComment('')

      const outcomeLabel =
        decision === 'approved' ? 'Approved' : decision === 'changes_requested' ? 'Changes Requested' : 'Rejected'
      setSuccessMsg(`Decision recorded: ${outcomeLabel} on v${updated.version}.`)
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error recording decision')
    } finally {
      setActionLoading(false)
    }
  }

  // Create a brand new submission
  const handleCreateSubmission = async () => {
    if (!newContent.trim()) {
      setErrorMsg('Content cannot be empty')
      return
    }
    setActionLoading(true)
    try {
      const creatorName = session ? session.user.email : 'Jordan Lee (Demo Creator)'
      const isDemoCreator = session ? session.is_demo : true
      const res = await apiFetch('/api/submissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTitle.trim() || 'New Campaign Copy',
          content: newContent,
          creator_name: creatorName,
          is_demo_creator: isDemoCreator,
        }),
      })

      if (!res.ok) throw new Error('Failed to create submission')

      const created: Submission = await res.json()
      setShowNewModal(false)
      setNewTitle('')
      setNewContent('')
      await refreshSubmissions(created.id)
      setSuccessMsg(`New submission '${created.title}' created in Draft state.`)
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error creating submission')
    } finally {
      setActionLoading(false)
    }
  }

  // Quick demo action to generate v2 with brand fixes applied
  const handleGenerateSampleRevision = async () => {
    if (!activeSubmission) return
    setActionLoading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      const revisedContent = activeSubmission.content
        .replace(/cheap headphones/gi, 'accessible high-fidelity audio')
        .replace(/\$199/g, '$299')
        .replace(/kills the competition/gi, 'leads the industry in acoustic clarity')
        .replace(/unbreakable build/gi, 'aerospace-grade aluminum durability')

      const res = await apiFetch(`/api/submissions/${activeSubmission.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: revisedContent,
          title: activeSubmission.title,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to create revision')
      }

      const updated: Submission = await res.json()
      setActiveSubmission(updated)
      setContent(updated.content)
      if (updated.latest_review_response) {
        setReviewResult(updated.latest_review_response)
      }
      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setSuccessMsg(`Revision v${updated.version} created with applied brand fixes. Compare with v${updated.version - 1} below.`)
      setActiveTab('diff')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error generating sample revision')
    } finally {
      setActionLoading(false)
    }
  }

  // Quick fix: Apply suggested correction to active content text
  const applyCorrection = (finding: Finding) => {
    if (!finding.suggested_correction) return

    let updated = content
    if (finding.category === 'required_disclaimer') {
      const disclaimer = finding.suggested_correction.replace('Add disclosure: ', '').trim()
      updated = `${content.trim()}\n\n${disclaimer}`
    } else if (finding.matched_text) {
      updated = updated.replace(finding.matched_text, finding.suggested_correction)
    }

    setContent(updated)
    runAudit(updated)
  }

  // Visual helper badges
  const getStatusBadge = (status: ReviewStatus, version: number) => {
    switch (status) {
      case 'draft':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            <FileText className="w-3.5 h-3.5 text-slate-400" />
            Draft v{version}
          </span>
        )
      case 'in_review':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            In Review v{version}
          </span>
        )
      case 'changes_requested':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-500/15 text-orange-300 border border-orange-500/30">
            <AlertCircle className="w-3.5 h-3.5 text-orange-400" />
            Changes Requested v{version}
          </span>
        )
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Approved v{version}
          </span>
        )
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            Rejected v{version}
          </span>
        )
    }
  }

  const getSeverityBadge = (sev: Severity) => {
    switch (sev) {
      case 'critical':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            Critical
          </span>
        )
      case 'warning':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Warning
          </span>
        )
      case 'info':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
            Style Info
          </span>
        )
    }
  }

  const getEvidenceBadge = (status: EvidenceStatus) => {
    switch (status) {
      case 'confirmed_violation':
        return (
          <span className="text-[11px] px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800">
            Confirmed Violation
          </span>
        )
      case 'potential_issue':
        return (
          <span className="text-[11px] px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800">
            Potential Issue
          </span>
        )
      case 'unverified_claim':
        return (
          <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            Unverified Claim
          </span>
        )
    }
  }

  const getCategoryLabel = (cat: string) => {
    switch (cat) {
      case 'prohibited_terminology':
        return 'Prohibited Term'
      case 'preferred_wording':
        return 'Brand Nomenclature'
      case 'fact_accuracy':
        return 'Approved Fact Contradiction'
      case 'required_disclaimer':
        return 'Mandatory Disclaimer'
      case 'brand_tone':
        return 'Brand Tone & Voice'
      case 'contextual_messaging':
        return 'Contextual Messaging'
      case 'unsupported_claim':
        return 'Unsupported Claim'
      case 'nuanced_inconsistency':
        return 'Nuanced Inconsistency'
      default:
        return cat.replace('_', ' ')
    }
  }

  const isContentDirty = activeSubmission ? content !== activeSubmission.content : false
  const wasApproved = activeSubmission?.status === 'approved'

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-30 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl shadow-inner">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Inkloom AI</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-slate-800 text-emerald-400 border border-slate-700">
                  Deterministic Engine
                </span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800 flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5" />
                  Gemini AI
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Hybrid Brand Governance: Rule Policy Auditor &bull; Gemini Contextual Analysis &bull; Human Review State Machine
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Storage Mode Badge */}
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${
                storageMode === 'supabase_persistent'
                  ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                  : 'bg-amber-950/40 border-amber-800/60 text-amber-300'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>
                {storageMode === 'supabase_persistent'
                  ? 'Supabase PostgreSQL (RLS)'
                  : 'Local Demo (In-Memory)'}
              </span>
            </div>

            {/* Backend connectivity */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`}
              />
              <span>{backendOnline ? 'API Connected' : 'API Disconnected'}</span>
            </div>

            {/* Brand Rules Drawer Toggle */}
            <button
              onClick={() => setShowRulesDrawer(!showRulesDrawer)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-xs font-medium text-slate-200 transition cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
              <span>Guidelines {demoRules?.is_demo && '(NovaSound Demo)'}</span>
              {showRulesDrawer ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>

            {/* User Session / Sign In Trigger */}
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
              {session ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200">
                    <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="font-medium max-w-[150px] truncate">{session.user.email}</span>
                    {session.role && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 font-mono uppercase">
                        {session.role}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={handleLogout}
                    className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs text-slate-300 border border-slate-700 transition cursor-pointer"
                    title="Sign Out"
                  >
                    Sign Out
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition shadow-sm cursor-pointer"
                >
                  <UserCheck className="w-3.5 h-3.5" />
                  <span>Sign In</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full p-6 md:p-8 flex-1 space-y-6">
        {/* Brand Rules Drawer (Collapsible) */}
        {showRulesDrawer && demoRules && (
          <div className="p-5 rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-emerald-400" />
                  Active Policy Config: {demoRules.brand_name}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Deterministic rules and certified facts loaded into the local engine
                </p>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                Demo Rules
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              {/* Prohibited Terms */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="font-semibold text-rose-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Prohibited Terminology ({demoRules.prohibited_terms.length})
                </span>
                <ul className="space-y-1.5 text-slate-400 max-h-48 overflow-y-auto">
                  {demoRules.prohibited_terms.map((r) => (
                    <li key={r.id} className="border-l-2 border-rose-500/40 pl-2">
                      <span className="text-slate-200 font-mono">"{r.term_or_pattern}"</span>
                      <p className="text-[11px] text-slate-400">{r.explanation}</p>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Preferred Wording */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="font-semibold text-sky-400 flex items-center gap-1.5">
                  <Wand2 className="w-3.5 h-3.5" />
                  Preferred Nomenclature ({demoRules.preferred_wording.length})
                </span>
                <ul className="space-y-1.5 text-slate-400 max-h-48 overflow-y-auto">
                  {demoRules.preferred_wording.map((r) => (
                    <li key={r.id} className="border-l-2 border-sky-500/40 pl-2">
                      <span className="text-slate-200 font-mono">"{r.avoid_term}"</span> &rarr;{' '}
                      <span className="text-emerald-400 font-mono">{r.preferred_term}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Approved Facts */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Approved Certified Facts ({demoRules.approved_facts.length})
                </span>
                <ul className="space-y-1.5 text-slate-400 max-h-48 overflow-y-auto">
                  {demoRules.approved_facts.map((f) => (
                    <li key={f.id} className="border-l-2 border-emerald-500/40 pl-2">
                      <div className="text-slate-200 font-medium">{f.entity}</div>
                      <div className="text-[11px] text-slate-400">
                        {f.attribute}: <span className="text-emerald-300 font-mono">{f.approved_value}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Required Disclaimers */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="font-semibold text-amber-400 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5" />
                  Required Disclaimers ({demoRules.required_disclaimers.length})
                </span>
                <ul className="space-y-1.5 text-slate-400 max-h-48 overflow-y-auto">
                  {demoRules.required_disclaimers.map((d) => (
                    <li key={d.id} className="border-l-2 border-amber-500/40 pl-2">
                      <div className="text-slate-200">{d.trigger_description}</div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate" title={d.required_disclaimer_text}>
                        {d.required_disclaimer_text}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================== */}
        {/* WORKFLOW LIFECYCLE BAR: Active Submission & State   */}
        {/* ==================================================== */}
        <section className="p-4 md:p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-850 border border-slate-800 shadow-xl space-y-3">
          {storageMode === 'local_demo' && (
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>
                  <strong>Demo Mode:</strong> Submissions are stored in local memory and reset upon server restart. Configure <code>SUPABASE_URL</code> and <code>SUPABASE_ANON_KEY</code> to enable persistent PostgreSQL storage with Row-Level Security.
                </span>
              </div>
            </div>
          )}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Left: Submission Selection & Metadata */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">
                  Submission:
                </span>
                <select
                  value={activeSubmission?.id || ''}
                  onChange={(e) => {
                    const found = submissions.find((s) => s.id === e.target.value)
                    if (found) handleSelectSubmission(found)
                  }}
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  {submissions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title} ({s.status} &bull; v{s.version})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setShowNewModal(true)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition cursor-pointer"
                  title="Create new copy submission"
                >
                  <Plus className="w-3.5 h-3.5 text-emerald-400" />
                  New
                </button>
              </div>

              {activeSubmission && (
                <div className="flex items-center gap-2">
                  {getStatusBadge(activeSubmission.status, activeSubmission.version)}
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/60 font-mono">
                    ID: {activeSubmission.id}
                  </span>
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded border font-medium ${
                      activeSubmission.storage_mode === 'supabase_persistent'
                        ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                        : 'bg-amber-950/40 text-amber-300 border-amber-800/60'
                    }`}
                  >
                    {activeSubmission.storage_mode === 'supabase_persistent'
                      ? 'PostgreSQL Persistent'
                      : 'Demo In-Memory'}
                  </span>
                </div>
              )}
            </div>

            {/* Right: Identities, Gemini Audit & Creator Action */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="flex items-center gap-1 text-slate-300">
                  <UserCheck className="w-3.5 h-3.5 text-sky-400" />
                  <span className="text-slate-400">Creator:</span>{' '}
                  <span className="font-medium text-slate-200">
                    {activeSubmission?.creator_name || 'Jordan Lee (Demo Creator)'}
                  </span>
                </span>
                <span className="text-slate-600">&bull;</span>
                <span className="flex items-center gap-1 text-slate-300">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-slate-400">Reviewer:</span>{' '}
                  <span className="font-medium text-slate-200">Alex Morgan (Demo Brand Guardian)</span>
                </span>
              </div>

              {/* Gemini Submission Audit Button */}
              {activeSubmission && (
                <button
                  type="button"
                  onClick={handleRunAiSubmissionAudit}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 text-xs font-semibold transition cursor-pointer"
                  title="Execute Gemini AI contextual audit on this submission copy"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                  Gemini Audit
                </button>
              )}

              {/* Creator Submit for Review Button */}
              {activeSubmission && (
                <button
                  type="button"
                  onClick={handleSubmitForReview}
                  disabled={
                    actionLoading ||
                    activeSubmission.status === 'in_review' ||
                    !content.trim()
                  }
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl font-semibold text-xs transition cursor-pointer ${
                    activeSubmission.status === 'in_review'
                      ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                      : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-md shadow-emerald-500/20'
                  }`}
                >
                  <Send className="w-3.5 h-3.5" />
                  {activeSubmission.status === 'in_review'
                    ? 'Awaiting Reviewer Decision'
                    : activeSubmission.status === 'changes_requested'
                    ? 'Re-submit for Review'
                    : 'Submit for Review'}
                </button>
              )}
            </div>
          </div>

          {/* CRITICAL GOVERNANCE PRINCIPLE NOTICE: Version Invalidation Banner */}
          {wasApproved && isContentDirty && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-start gap-2.5 animate-in fade-in">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-200">Content Modified Post-Approval:</span>{' '}
                Previous approval is locked to v{activeSubmission?.version} snapshot. Saving these modifications will
                increment version to v{(activeSubmission?.version || 1) + 1}, reset status to Draft, and require
                a fresh human review cycle before publication.
              </div>
            </div>
          )}

          {activeSubmission &&
            activeSubmission.status === 'draft' &&
            activeSubmission.version > 1 &&
            activeSubmission.decision_history.some((d) => d.decision === 'approved') && (
              <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <Info className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                <span>
                  Approval was invalidated because content changed to v{activeSubmission.version}. Submit for review
                  to certify this new version.
                </span>
              </div>
            )}
        </section>

        {/* Global Notifications / Feedback */}
        {successMsg && (
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </div>
            <button onClick={() => setSuccessMsg(null)} className="text-slate-400 hover:text-white text-xs">
              &times;
            </button>
          </div>
        )}

        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-slate-400 hover:text-white text-xs">
              &times;
            </button>
          </div>
        )}

        {/* Studio Workspace: Editor + Dual-Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Content Editor (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4 shadow-lg">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-emerald-400" />
                  Content Under Review
                </label>
                <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                  {isContentDirty && (
                    <span className="text-[11px] text-amber-400 font-sans font-medium">Unsaved edits</span>
                  )}
                  <span>{content.length} chars</span>
                </div>
              </div>

              {/* Title input */}
              {activeSubmission && (
                <div>
                  <input
                    type="text"
                    value={submissionTitle}
                    onChange={(e) => setSubmissionTitle(e.target.value)}
                    placeholder="Campaign submission title..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              )}

              {/* Preset Copy Loader */}
              <div className="space-y-1.5">
                <span className="text-[11px] text-slate-400 font-medium">Load Realistic Test Scenarios:</span>
                <div className="flex flex-wrap gap-1.5">
                  {SAMPLE_COPY_OPTIONS.map((opt, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setContent(opt.text)
                        runAudit(opt.text)
                      }}
                      className="text-[11px] px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/80 transition cursor-pointer"
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Textarea */}
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={9}
                placeholder="Paste marketing copy, press releases, or product descriptions here..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-mono transition leading-relaxed resize-y"
              />

              {/* Action Buttons & AI Toggle */}
              <div className="flex items-center justify-between pt-2 flex-wrap gap-2">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setContent('')
                      setReviewResult(null)
                    }}
                    className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Clear
                  </button>

                  {/* AI toggle checkbox */}
                  <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={includeAi}
                      onChange={(e) => setIncludeAi(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                    />
                    <Sparkles className={`w-3.5 h-3.5 ${includeAi ? 'text-sky-400' : 'text-slate-500'}`} />
                    <span>Gemini AI</span>
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  {activeSubmission && isContentDirty && (
                    <button
                      type="button"
                      onClick={handleSaveSubmission}
                      disabled={actionLoading}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs border border-slate-700 transition cursor-pointer"
                    >
                      <RefreshCw className={`w-3 h-3 ${actionLoading ? 'animate-spin' : ''}`} />
                      Save Draft {wasApproved && '(Resets Approval)'}
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => runAudit()}
                    disabled={loading || !content.trim()}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-semibold text-xs tracking-wide shadow-lg shadow-emerald-500/20 transition cursor-pointer"
                  >
                    <Sparkles className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    {loading ? 'Evaluating Policy...' : includeAi ? 'Run Audit + Gemini AI' : 'Run Deterministic Audit'}
                  </button>
                </div>
              </div>
            </div>

            {/* Quick status card for active submission */}
            {activeSubmission && (
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-xs space-y-2">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Current Version:</span>
                  <span className="font-mono text-slate-200 font-bold">v{activeSubmission.version}</span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Lifecycle Status:</span>
                  <span className="font-semibold text-slate-200 uppercase tracking-wide">
                    {activeSubmission.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Decisions Recorded:</span>
                  <span className="font-mono text-slate-200 font-bold">
                    {activeSubmission.decision_history.length}
                  </span>
                </div>
                {activeSubmission.submitted_at && (
                  <div className="flex items-center justify-between text-slate-400">
                    <span>Last Submitted:</span>
                    <span className="font-mono text-slate-300 text-[11px]">
                      {new Date(activeSubmission.submitted_at).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Dual Tabs (Policy Audit vs Human Decision & Audit Trail) (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            {/* Tab navigation */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('audit')}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    activeTab === 'audit'
                      ? 'bg-slate-800 text-white border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  Policy Audit
                  {reviewResult && (
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                        reviewResult.total_findings > 0
                          ? 'bg-rose-500/20 text-rose-300'
                          : 'bg-emerald-500/20 text-emerald-300'
                      }`}
                    >
                      {reviewResult.total_findings}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('workflow')}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    activeTab === 'workflow'
                      ? 'bg-slate-800 text-white border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <History className="w-3.5 h-3.5 text-sky-400" />
                  Human Review & Decisions
                  {activeSubmission && activeSubmission.decision_history.length > 0 && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-sky-500/20 text-sky-300">
                      {activeSubmission.decision_history.length}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('diff')}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    activeTab === 'diff'
                      ? 'bg-slate-800 text-white border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <GitCompare className="w-3.5 h-3.5 text-sky-400" />
                  Compare Revisions
                  {activeSubmission && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-sky-500/20 text-sky-300 font-mono">
                      v{activeSubmission.version}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('guidelines')}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    activeTab === 'guidelines'
                      ? 'bg-slate-800 text-white border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                  Guidelines Editor
                  {demoRules && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-700 text-slate-300 font-mono">
                      {demoRules.prohibited_terms.length +
                        demoRules.preferred_wording.length +
                        demoRules.approved_facts.length +
                        demoRules.required_disclaimers.length}
                    </span>
                  )}
                </button>
              </div>

              {activeSubmission?.status === 'in_review' && (
                <span className="flex items-center gap-1.5 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  Awaiting Reviewer Action
                </span>
              )}
            </div>

            {/* TAB 1: Hybrid Policy Audit (Deterministic + Gemini AI) */}
            {activeTab === 'audit' && (
              <div className="space-y-4">
                {reviewResult ? (
                  <div className="space-y-4">
                    {/* Compliance Banner */}
                    <div
                      className={`p-4 rounded-2xl border flex items-center justify-between ${
                        reviewResult.is_compliant
                          ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                          : 'bg-slate-900/80 border-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        {reviewResult.is_compliant ? (
                          <div className="p-2 bg-emerald-500/20 rounded-xl text-emerald-400">
                            <CheckCircle2 className="w-6 h-6" />
                          </div>
                        ) : (
                          <div className="p-2 bg-amber-500/20 rounded-xl text-amber-400">
                            <AlertTriangle className="w-6 h-6" />
                          </div>
                        )}
                        <div>
                          <h4 className="text-sm font-bold text-white">
                            {reviewResult.is_compliant
                              ? '100% Brand Compliant'
                              : `${reviewResult.total_findings} Policy Finding${
                                  reviewResult.total_findings > 1 ? 's' : ''
                                } Identified`}
                          </h4>
                          <p className="text-xs text-slate-400">
                            Evaluated against {reviewResult.brand_name}{' '}
                            {reviewResult.is_demo_data && '(Sample Governance Rules)'}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium">
                          {reviewResult.findings_by_severity.critical} Critical
                        </span>
                        <span className="text-xs px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                          {reviewResult.findings_by_severity.warning} Warning
                        </span>
                        <span className="text-xs px-2.5 py-1 rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">
                          {reviewResult.findings_by_severity.info} Style Info
                        </span>
                      </div>
                    </div>

                    {/* Gemini AI Status Card */}
                    {reviewResult.ai_status === 'completed' && (
                      <div className="p-4 rounded-xl bg-gradient-to-r from-sky-950/40 via-slate-900 to-indigo-950/30 border border-sky-500/30 space-y-1.5 animate-in fade-in">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-sky-400" />
                            <span className="text-xs font-bold text-white">Gemini Contextual AI Analysis</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-900/60 text-sky-300 border border-sky-700">
                              {reviewResult.ai_model || 'gemini-2.5-flash'}
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-400">
                            {reviewResult.deterministic_count ?? 0} rule &bull; {reviewResult.ai_count ?? 0} AI findings
                          </span>
                        </div>
                        {reviewResult.ai_summary && (
                          <p className="text-xs text-slate-300 leading-relaxed font-sans italic">
                            "{reviewResult.ai_summary}"
                          </p>
                        )}
                      </div>
                    )}

                    {reviewResult.ai_status === 'unavailable' && (
                      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-start gap-2">
                        <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold text-amber-200">Gemini AI Analysis Unavailable:</span>{' '}
                          {reviewResult.ai_error || 'GEMINI_API_KEY environment variable is not configured on the backend.'}{' '}
                          Deterministic rule engine evaluated successfully.
                        </div>
                      </div>
                    )}

                    {reviewResult.ai_status === 'failed' && (
                      <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold text-rose-200">Gemini AI Analysis Notice:</span>{' '}
                          {reviewResult.ai_error}. Deterministic findings are preserved.
                        </div>
                      </div>
                    )}

                    {/* Findings list */}
                    {reviewResult.findings.length === 0 ? (
                      <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <h5 className="text-sm font-semibold text-slate-200">No Policy Violations Found</h5>
                        <p className="text-xs text-slate-400 max-w-md mx-auto">
                          Submitted copy adheres strictly to prohibited vocabulary rules, approved fact assertions,
                          required regulatory disclaimers, brand tone, and preferred terminology.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {reviewResult.findings.map((finding) => (
                          <div
                            key={finding.id}
                            className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700/80 transition space-y-3"
                          >
                            {/* Badges */}
                            <div className="flex items-center justify-between flex-wrap gap-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-xs font-mono font-bold text-slate-400">
                                  {finding.id}
                                </span>

                                {/* Source badge: Deterministic vs Gemini AI */}
                                {finding.source === 'gemini_ai' ? (
                                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 font-medium">
                                    <Sparkles className="w-3 h-3 text-sky-400" />
                                    Gemini AI Contextual
                                    {finding.confidence !== undefined && finding.confidence !== null && (
                                      <span className="text-[10px] opacity-80 font-mono">
                                        ({Math.round(finding.confidence * 100)}%)
                                      </span>
                                    )}
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
                                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                                    Deterministic Rule
                                  </span>
                                )}

                                <span className="text-xs font-medium text-slate-300 bg-slate-800 px-2 py-0.5 rounded">
                                  {getCategoryLabel(finding.category)}
                                </span>
                                {getSeverityBadge(finding.severity)}
                              </div>
                              {getEvidenceBadge(finding.evidence_status)}
                            </div>

                            {/* Matched text quote */}
                            {finding.matched_text && (
                              <div className="flex items-center gap-2 text-xs">
                                <span className="text-slate-400">Matched evidence:</span>
                                <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 font-mono border border-rose-500/20 font-medium">
                                  "{finding.matched_text}"
                                </span>
                                {finding.start_index !== null && (
                                  <span className="text-[11px] text-slate-400 font-mono">
                                    [offset {finding.start_index}:{finding.end_index}]
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Rule and Explanation */}
                            <div className="space-y-1 text-xs">
                              <p className="text-slate-300 leading-relaxed">{finding.explanation}</p>
                              <div className="text-[11px] text-slate-400 font-mono">
                                Basis: {finding.rule_name_or_fact}
                              </div>
                            </div>

                            {/* Actionable Suggestion */}
                            {finding.suggested_correction && (
                              <div className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-slate-950/80 border border-slate-800">
                                <div className="text-xs">
                                  <span className="text-slate-400">Suggested Action: </span>
                                  <span className="text-emerald-400 font-mono font-medium">
                                    {finding.suggested_correction}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => applyCorrection(finding)}
                                  className="shrink-0 flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-medium transition cursor-pointer"
                                >
                                  Apply Fix
                                  <ArrowRight className="w-3 h-3" />
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3">
                    <ShieldCheck className="w-10 h-10 text-slate-600 mx-auto" />
                    <h4 className="text-sm font-semibold text-slate-300">Ready for Governance Review</h4>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      Click "Run Policy Audit" above or choose a sample scenario to evaluate content against active
                      prohibited terms, certified facts, mandatory disclaimers, and contextual brand tone.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Human Review Decision Gate & Audit Trail */}
            {activeTab === 'workflow' && (
              <div className="space-y-6">
                {/* 1. Reviewer Decision Station */}
                <div className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        <UserCheck className="w-4 h-4 text-sky-400" />
                        Human Reviewer Decision Gate
                      </h4>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Brand Guardian: Alex Morgan (Certified Reviewer &bull; Demo Identity)
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {activeSubmission && getStatusBadge(activeSubmission.status, activeSubmission.version)}
                      {activeSubmission && activeSubmission.version > 1 && (
                        <button
                          type="button"
                          onClick={() => setActiveTab('diff')}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 text-xs font-semibold transition cursor-pointer"
                          title="View revision diff"
                        >
                          <GitCompare className="w-3.5 h-3.5 text-sky-400" />
                          Compare Revisions
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Decision Guidance State */}
                  {activeSubmission?.status !== 'in_review' ? (
                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400 space-y-2">
                      <div className="flex items-center gap-2 text-slate-300 font-medium">
                        <Info className="w-4 h-4 text-sky-400" />
                        Reviewer actions disabled while submission is in '{activeSubmission?.status}' status.
                      </div>
                      <p className="text-slate-400">
                        Content must be submitted by the creator (status must be 'In Review') before an approval,
                        change request, or rejection can be recorded. AI analysis advises human reviewers but never approves automatically.
                      </p>
                      {activeSubmission?.status === 'draft' && (
                        <button
                          type="button"
                          onClick={handleSubmitForReview}
                          disabled={actionLoading}
                          className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs transition cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5" />
                          Submit v{activeSubmission.version} For Review Now
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* High-severity findings reminder */}
                      {reviewResult && reviewResult.findings_by_severity.critical > 0 && (
                        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold text-rose-200">
                              {reviewResult.findings_by_severity.critical} Critical Violations Found:
                            </span>{' '}
                            Human reviewers are advised to request changes or reject content that fails core brand
                            guidelines.
                          </div>
                        </div>
                      )}

                      {/* Reviewer Comment Input */}
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
                            Reviewer Feedback / Decision Comment:
                          </span>
                          <span className="text-[11px] text-slate-500">
                            Required for 'Request Changes' & 'Reject'
                          </span>
                        </label>
                        <textarea
                          value={reviewerComment}
                          onChange={(e) => {
                            setReviewerComment(e.target.value)
                            if (commentError) setCommentError(null)
                          }}
                          rows={3}
                          placeholder="Provide rationale or required changes (Mandatory for rejection / change requests)..."
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500 font-sans"
                        />
                        {commentError && (
                          <p className="text-xs text-rose-400 flex items-center gap-1 font-medium">
                            <AlertCircle className="w-3.5 h-3.5" />
                            {commentError}
                          </p>
                        )}
                      </div>

                      {/* Action Decision Buttons */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
                        {/* 1. Approve */}
                        <button
                          type="button"
                          onClick={() => handleRecordDecision('approved')}
                          disabled={actionLoading}
                          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 font-semibold text-xs transition cursor-pointer"
                        >
                          <Check className="w-4 h-4 text-emerald-400" />
                          Approve Copy
                        </button>

                        {/* 2. Request Changes */}
                        <button
                          type="button"
                          onClick={() => handleRecordDecision('changes_requested')}
                          disabled={actionLoading}
                          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 font-semibold text-xs transition cursor-pointer"
                        >
                          <AlertCircle className="w-4 h-4 text-amber-400" />
                          Request Changes
                        </button>

                        {/* 3. Reject */}
                        <button
                          type="button"
                          onClick={() => handleRecordDecision('rejected')}
                          disabled={actionLoading}
                          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 font-semibold text-xs transition cursor-pointer"
                        >
                          <X className="w-4 h-4 text-rose-400" />
                          Reject Copy
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* 2. Immutable Decision History & Audit Trail */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <History className="w-3.5 h-3.5 text-sky-400" />
                      Decision History & Audit Trail ({activeSubmission?.decision_history.length || 0})
                    </h4>
                    <span className="text-[11px] text-slate-500 font-mono">
                      Version Snapshots Tied to Approval
                    </span>
                  </div>

                  {activeSubmission?.decision_history.length === 0 ? (
                    <div className="p-8 text-center rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400">
                      No decisions recorded yet for this submission.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {activeSubmission?.decision_history.map((record) => (
                        <div
                          key={record.id}
                          className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs"
                        >
                          {/* Record header */}
                          <div className="flex items-center justify-between flex-wrap gap-2">
                            <div className="flex items-center gap-2">
                              {record.decision === 'approved' && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold text-[11px]">
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  Approved
                                </span>
                              )}
                              {record.decision === 'changes_requested' && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-orange-500/15 text-orange-300 border border-orange-500/30 font-semibold text-[11px]">
                                  <AlertCircle className="w-3 h-3 text-orange-400" />
                                  Changes Requested
                                </span>
                              )}
                              {record.decision === 'rejected' && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30 font-semibold text-[11px]">
                                  <X className="w-3 h-3 text-rose-400" />
                                  Rejected
                                </span>
                              )}
                              <span className="font-mono text-slate-300 font-bold">
                                Version v{record.content_version}
                              </span>
                            </div>

                            <span className="text-[11px] font-mono text-slate-400">
                              {new Date(record.timestamp).toLocaleString()}
                            </span>
                          </div>

                          {/* Reviewer & Comment */}
                          <div className="space-y-1">
                            <div className="text-[11px] text-slate-400 flex items-center gap-1">
                              <span>Reviewer:</span>
                              <span className="text-slate-200 font-medium">{record.reviewer_name}</span>
                              {record.is_demo_reviewer && (
                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                                  Demo ID
                                </span>
                              )}
                            </div>
                            {record.comment && (
                              <p className="text-slate-300 bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80 font-sans italic">
                                "{record.comment}"
                              </p>
                            )}
                          </div>

                          {/* Snapshot toggle */}
                          <div className="pt-1 flex items-center justify-between border-t border-slate-800/60">
                            <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                              <span>Findings at review:</span>
                              <span className="text-rose-400">
                                {record.findings_summary?.critical || 0} crit
                              </span>
                              <span>&bull;</span>
                              <span className="text-amber-400">
                                {record.findings_summary?.warning || 0} warn
                              </span>
                            </div>

                            <button
                              type="button"
                              onClick={() =>
                                setExpandedSnapshotId(
                                  expandedSnapshotId === record.id ? null : record.id
                                )
                              }
                              className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 cursor-pointer"
                            >
                              {expandedSnapshotId === record.id ? 'Hide Snapshot' : 'View Text Snapshot'}
                            </button>
                          </div>

                          {/* Expanded content snapshot */}
                          {expandedSnapshotId === record.id && (
                            <div className="mt-2 p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 space-y-1 animate-in fade-in">
                              <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-sans">
                                Evaluated Content Snapshot (v{record.content_version}):
                              </span>
                              <p className="whitespace-pre-wrap leading-relaxed">{record.content_snapshot}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: Compare Revisions & Diff View */}
            {activeTab === 'diff' && activeSubmission && (
              <RevisionDiffViewer
                submission={activeSubmission}
                apiBase={API_BASE}
                authHeaders={getAuthHeaders(session)}
                onApplyFix={applyCorrection}
                onGenerateSampleRevision={handleGenerateSampleRevision}
              />
            )}

            {/* TAB 4: Brand Guidelines & Policy Editor */}
            {activeTab === 'guidelines' && demoRules && (
              <BrandGuidelinesEditor
                initialRules={demoRules}
                onSave={handleSaveGuidelines}
                onReset={handleResetGuidelines}
                isSaving={actionLoading}
              />
            )}
          </div>
        </div>
      </main>

      {/* New Submission Modal */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4 animate-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-400" />
                Create New Content Submission
              </h3>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="text-slate-400 hover:text-white text-xs cursor-pointer"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Submission Title</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Summer Campaign Social Ad"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Content Copy</label>
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  rows={5}
                  placeholder="Paste marketing copy..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="text-[11px] text-slate-400">
                Created with demo creator identity:{' '}
                <span className="text-slate-300 font-medium">Jordan Lee (Demo Creator)</span>. Initial status
                will be <span className="text-emerald-400 font-medium">Draft v1</span>.
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="px-3.5 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateSubmission}
                disabled={actionLoading || !newContent.trim()}
                className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs shadow-md shadow-emerald-500/20 disabled:opacity-50 cursor-pointer"
              >
                {actionLoading ? 'Creating...' : 'Create Draft'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative space-y-4">
            <button
              onClick={() => {
                setShowAuthModal(false)
                setAuthError(null)
              }}
              className="absolute top-4 right-4 text-slate-400 hover:text-white transition cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">Inkloom Authentication</h3>
                <p className="text-xs text-slate-400">
                  {storageMode === 'supabase_persistent'
                    ? 'Sign in with your Supabase credentials'
                    : 'Select a demo persona or sign in with Supabase'}
                </p>
              </div>
            </div>

            {authError && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{authError}</span>
              </div>
            )}

            {/* Quick Demo Switcher when running in Local Demo Mode */}
            {storageMode === 'local_demo' && (
              <div className="space-y-2 p-3 rounded-xl bg-slate-950 border border-slate-800">
                <p className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  Local Demo Mode Personas:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => handleLogin(undefined, 'jordan.lee@novasound.example')}
                    className="p-2 text-left rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs transition cursor-pointer"
                  >
                    <p className="font-semibold text-white">Jordan Lee</p>
                    <p className="text-[10px] text-slate-400">Creator</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleLogin(undefined, 'alex.rivera@novasound.example')}
                    className="p-2 text-left rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs transition cursor-pointer"
                  >
                    <p className="font-semibold text-white">Alex Rivera</p>
                    <p className="text-[10px] text-amber-400 font-medium">Reviewer</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleLogin(undefined, 'morgan.vance@novasound.example')}
                    className="p-2 text-left rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs transition cursor-pointer"
                  >
                    <p className="font-semibold text-white">Morgan Vance</p>
                    <p className="text-[10px] text-sky-400 font-medium">Admin / Owner</p>
                  </button>
                </div>
              </div>
            )}

            {/* Standard Credential Form */}
            <form onSubmit={handleLogin} className="space-y-3 pt-1">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
                <input
                  type="email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  placeholder="user@novasound.example"
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAuthModal(false)
                    setAuthError(null)
                  }}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs text-slate-300 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-semibold text-white transition cursor-pointer flex items-center gap-1.5"
                >
                  {authLoading ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <UserCheck className="w-3.5 h-3.5" />
                  )}
                  <span>Sign In</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-xs text-slate-400 bg-slate-900/30">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Inkloom AI &copy; 2026. Brand Governance & Content Policy Auditor.</span>
          <span>Deterministic Rule Engine &bull; Gemini Contextual AI &bull; Human Review State Machine</span>
        </div>
      </footer>
    </div>
  )
}

export default App
