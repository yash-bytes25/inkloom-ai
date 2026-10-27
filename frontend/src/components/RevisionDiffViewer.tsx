import React, { useState, useEffect } from 'react'
import {
  GitCompare,
  ArrowRight,
  ArrowLeftRight,
  CheckCircle2,
  AlertTriangle,
  PlusCircle,
  FileText,
  Clock,
  Columns,
  Rows,
  Sparkles,
  RefreshCw,
  Info,
} from 'lucide-react'
import type {
  Submission,
  RevisionDiffResponse,
  Finding,
  Severity,
} from '../types/governance'

interface RevisionDiffViewerProps {
  submission: Submission
  apiBase: string
  authHeaders?: Record<string, string>
  onApplyFix?: (finding: Finding) => void
  onGenerateSampleRevision?: () => Promise<void>
}

export const RevisionDiffViewer: React.FC<RevisionDiffViewerProps> = ({
  submission,
  apiBase,
  authHeaders,
  onApplyFix,
  onGenerateSampleRevision,
}) => {
  const [diffData, setDiffData] = useState<RevisionDiffResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [layoutMode, setLayoutMode] = useState<'side-by-side' | 'stacked'>('side-by-side')
  const [activeFindingTab, setActiveFindingTab] = useState<'all' | 'resolved' | 'unresolved' | 'introduced'>('all')

  // Version selectors
  const latestVer = submission.version
  const defaultOrig = latestVer > 1 ? latestVer - 1 : 1
  const [origVersion, setOrigVersion] = useState<number>(defaultOrig)
  const [newerVersion, setNewerVersion] = useState<number>(latestVer)

  // Fetch diff from backend
  const fetchDiff = async (orig: number, newer: number) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${apiBase}/api/submissions/${submission.id}/diff?orig=${orig}&newer=${newer}`,
        {
          headers: {
            ...(authHeaders || {}),
          },
        }
      )
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to fetch diff (${res.status})`)
      }
      const data: RevisionDiffResponse = await res.json()
      setDiffData(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error computing revision diff')
    } finally {
      setLoading(false)
    }
  }

  // Update versions and trigger fetch when submission changes or version changes
  useEffect(() => {
    const updatedLatest = submission.version
    const updatedOrig = updatedLatest > 1 ? updatedLatest - 1 : 1
    setOrigVersion(updatedOrig)
    setNewerVersion(updatedLatest)
    fetchDiff(updatedOrig, updatedLatest)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submission.id, submission.version])

  const handleOrigChange = (newOrig: number) => {
    setOrigVersion(newOrig)
    fetchDiff(newOrig, newerVersion)
  }

  const handleNewerChange = (newNewer: number) => {
    setNewerVersion(newNewer)
    fetchDiff(origVersion, newNewer)
  }

  const handleSwapVersions = () => {
    const temp = origVersion
    setOrigVersion(newerVersion)
    setNewerVersion(temp)
    fetchDiff(newerVersion, temp)
  }

  const getSeverityBadge = (sev: Severity) => {
    switch (sev) {
      case 'critical':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
            Critical
          </span>
        )
      case 'warning':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
            Warning
          </span>
        )
      case 'info':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/15 text-sky-300 border border-sky-500/30">
            Info
          </span>
        )
    }
  }

  const availableVersions = diffData?.available_versions || [1]

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* 1. Header Toolbar: Selectors & Status */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-sky-400" />
              Revision Diff & Governance Comparison
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Compare content versions side-by-side with verified finding resolution tracking.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            {/* View Mode Toggle */}
            <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                type="button"
                onClick={() => setLayoutMode('side-by-side')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition cursor-pointer ${
                  layoutMode === 'side-by-side'
                    ? 'bg-slate-800 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Side-by-Side Columns"
              >
                <Columns className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Side-by-Side</span>
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('stacked')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition cursor-pointer ${
                  layoutMode === 'stacked'
                    ? 'bg-slate-800 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Stacked Layout"
              >
                <Rows className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Stacked</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => fetchDiff(origVersion, newerVersion)}
              disabled={loading}
              className="p-2 rounded-xl bg-slate-850 hover:bg-slate-800 text-slate-300 border border-slate-700 transition cursor-pointer"
              title="Refresh Diff"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Version Pickers & Active State */}
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center flex-wrap gap-2">
            <span className="text-slate-400 font-medium">Comparing:</span>

            {/* Original Version Selector */}
            <div className="flex items-center gap-1.5 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
              <span className="text-[11px] text-rose-400 font-bold uppercase">Base</span>
              <select
                value={origVersion}
                onChange={(e) => handleOrigChange(Number(e.target.value))}
                className="bg-transparent text-white font-semibold focus:outline-none cursor-pointer"
              >
                {availableVersions.map((v) => (
                  <option key={`orig-${v}`} value={v} className="bg-slate-900 text-slate-200">
                    Version v{v} {v === 1 ? '(Initial Draft)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleSwapVersions}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
              title="Swap Base and Comparison Versions"
            >
              <ArrowLeftRight className="w-3.5 h-3.5" />
            </button>

            {/* Newer Version Selector */}
            <div className="flex items-center gap-1.5 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
              <span className="text-[11px] text-emerald-400 font-bold uppercase">Target</span>
              <select
                value={newerVersion}
                onChange={(e) => handleNewerChange(Number(e.target.value))}
                className="bg-transparent text-white font-semibold focus:outline-none cursor-pointer"
              >
                {availableVersions.map((v) => (
                  <option key={`newer-${v}`} value={v} className="bg-slate-900 text-slate-200">
                    Version v{v} {v === submission.version ? '(Current Active)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Submission Active Status Badge */}
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span>Current Submission:</span>
            <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
              v{submission.version} &bull; {submission.status.replace('_', ' ')}
            </span>
          </div>
        </div>

        {/* Warning if only 1 version exists */}
        {availableVersions.length <= 1 && (
          <div className="p-3 rounded-xl bg-sky-950/30 border border-sky-500/20 text-xs text-sky-300 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-sky-400 shrink-0" />
              <span>
                Submission is at initial draft (v1). Modify copy and save to generate v2, or click to create a demo
                revision with applied fixes.
              </span>
            </div>
            {onGenerateSampleRevision && (
              <button
                type="button"
                onClick={onGenerateSampleRevision}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-semibold transition cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Generate Demo Revision v2
              </button>
            )}
          </div>
        )}

        {/* Historical comparison banner if comparing non-active versions */}
        {newerVersion !== submission.version && (
          <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>
              Comparing historical versions v{origVersion} and v{newerVersion}. Active draft is currently at v{submission.version}.
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 2. Statistical Change Ribbon */}
      {diffData && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Card 1: Text Changes */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block">
              Content Modifications
            </span>
            <div className="flex items-baseline gap-2 font-mono">
              <span className="text-emerald-400 text-sm font-bold">+{diffData.stats.additions}</span>
              <span className="text-rose-400 text-sm font-bold">-{diffData.stats.deletions}</span>
              <span className="text-sky-400 text-xs">~{diffData.stats.modifications} modified</span>
            </div>
          </div>

          {/* Card 2: Resolved Findings */}
          <div
            onClick={() => setActiveFindingTab('resolved')}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              activeFindingTab === 'resolved'
                ? 'bg-emerald-950/40 border-emerald-500/50 shadow-lg shadow-emerald-950/20'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Resolved Violations
              </span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-lg font-bold text-emerald-300 font-mono">
                {diffData.findings_summary.resolved_count}
              </span>
              <span className="text-[11px] text-emerald-400/80">eliminated</span>
            </div>
          </div>

          {/* Card 3: Unresolved Findings */}
          <div
            onClick={() => setActiveFindingTab('unresolved')}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              activeFindingTab === 'unresolved'
                ? 'bg-amber-950/40 border-amber-500/50 shadow-lg shadow-amber-950/20'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Unresolved Violations
              </span>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-lg font-bold text-amber-300 font-mono">
                {diffData.findings_summary.unresolved_count}
              </span>
              <span className="text-[11px] text-amber-400/80">still active</span>
            </div>
          </div>

          {/* Card 4: Introduced Findings */}
          <div
            onClick={() => setActiveFindingTab('introduced')}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              activeFindingTab === 'introduced'
                ? 'bg-rose-950/40 border-rose-500/50 shadow-lg shadow-rose-950/20'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Introduced Violations
              </span>
              <PlusCircle className="w-3.5 h-3.5 text-rose-400" />
            </div>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-lg font-bold text-rose-300 font-mono">
                {diffData.findings_summary.introduced_count}
              </span>
              <span className="text-[11px] text-rose-400/80">new issues</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Side-by-Side / Stacked Diff Box */}
      {diffData && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl">
          {/* Box Header */}
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-800 bg-slate-900/90 text-xs font-semibold">
            {/* Left Header */}
            <div className="p-3 flex items-center justify-between text-rose-300 bg-rose-950/20">
              <span className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-rose-400" />
                Original Revision v{diffData.orig_version}
              </span>
              <span className="text-[11px] text-slate-400 font-mono font-normal">
                {new Date(diffData.orig_timestamp).toLocaleTimeString()} &bull; {diffData.orig_creator || 'Creator'}
              </span>
            </div>

            {/* Right Header */}
            <div className="p-3 flex items-center justify-between text-emerald-300 bg-emerald-950/20">
              <span className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                Newer Revision v{diffData.newer_version}
              </span>
              <span className="text-[11px] text-slate-400 font-mono font-normal">
                {new Date(diffData.newer_timestamp).toLocaleTimeString()} &bull; {diffData.newer_creator || 'Creator'}
              </span>
            </div>
          </div>

          {/* Diff Lines Container */}
          <div
            className={`font-mono text-xs overflow-x-auto divide-y divide-slate-900/80 max-h-[500px] overflow-y-auto ${
              layoutMode === 'side-by-side' ? 'grid grid-cols-1' : 'space-y-0'
            }`}
          >
            {diffData.lines.length === 0 ? (
              <div className="p-8 text-center text-slate-500 font-sans">
                Both revisions have identical content text.
              </div>
            ) : (
              diffData.lines.map((line, idx) => {
                if (layoutMode === 'side-by-side') {
                  return (
                    <div
                      key={`line-${idx}`}
                      className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-800/80 hover:bg-slate-900/30 transition-colors"
                    >
                      {/* Left: Original line */}
                      <div
                        className={`flex items-start p-1.5 gap-2 ${
                          line.type === 'delete'
                            ? 'bg-rose-950/30 text-rose-300 border-l-2 border-rose-500'
                            : line.type === 'replace'
                            ? 'bg-rose-950/15 text-slate-300 border-l-2 border-rose-500/40'
                            : 'text-slate-400'
                        }`}
                      >
                        <span className="select-none text-[10px] text-slate-600 font-mono w-7 text-right shrink-0">
                          {line.line_number_orig ?? ''}
                        </span>
                        <div className="whitespace-pre-wrap break-words leading-relaxed flex-1">
                          {line.orig_segments && line.orig_segments.length > 0 ? (
                            line.orig_segments.map((seg, sIdx) => (
                              <span
                                key={`orig-seg-${sIdx}`}
                                className={
                                  seg.type === 'delete'
                                    ? 'bg-rose-500/25 text-rose-200 line-through rounded px-0.5'
                                    : ''
                                }
                              >
                                {seg.text}
                              </span>
                            ))
                          ) : (
                            <span>{line.orig_text || ' '}</span>
                          )}
                        </div>
                      </div>

                      {/* Right: Newer line */}
                      <div
                        className={`flex items-start p-1.5 gap-2 ${
                          line.type === 'insert'
                            ? 'bg-emerald-950/30 text-emerald-300 border-l-2 border-emerald-500'
                            : line.type === 'replace'
                            ? 'bg-emerald-950/15 text-slate-200 border-l-2 border-emerald-500/40'
                            : 'text-slate-300'
                        }`}
                      >
                        <span className="select-none text-[10px] text-slate-600 font-mono w-7 text-right shrink-0">
                          {line.line_number_newer ?? ''}
                        </span>
                        <div className="whitespace-pre-wrap break-words leading-relaxed flex-1">
                          {line.newer_segments && line.newer_segments.length > 0 ? (
                            line.newer_segments.map((seg, sIdx) => (
                              <span
                                key={`newer-seg-${sIdx}`}
                                className={
                                  seg.type === 'insert'
                                    ? 'bg-emerald-500/25 text-emerald-200 font-semibold rounded px-0.5'
                                    : ''
                                }
                              >
                                {seg.text}
                              </span>
                            ))
                          ) : (
                            <span>{line.newer_text || ' '}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                }

                // Stacked mode
                return (
                  <div key={`line-stack-${idx}`} className="p-2 space-y-1">
                    {line.orig_text && line.type !== 'equal' && (
                      <div className="flex items-start gap-2 bg-rose-950/25 text-rose-300 p-1 rounded border-l-2 border-rose-500">
                        <span className="text-[10px] text-rose-400 font-bold shrink-0">- v{diffData.orig_version}</span>
                        <span className="whitespace-pre-wrap leading-relaxed">{line.orig_text}</span>
                      </div>
                    )}
                    {line.newer_text && line.type !== 'equal' && (
                      <div className="flex items-start gap-2 bg-emerald-950/25 text-emerald-300 p-1 rounded border-l-2 border-emerald-500">
                        <span className="text-[10px] text-emerald-400 font-bold shrink-0">+ v{diffData.newer_version}</span>
                        <span className="whitespace-pre-wrap leading-relaxed">{line.newer_text}</span>
                      </div>
                    )}
                    {line.type === 'equal' && (
                      <div className="flex items-start gap-2 text-slate-400 p-1">
                        <span className="text-[10px] text-slate-600 w-6 text-right shrink-0">
                          {line.line_number_newer}
                        </span>
                        <span className="whitespace-pre-wrap leading-relaxed">{line.newer_text}</span>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* 4. Governance Impact Breakdown */}
      {diffData && (
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
            <div>
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Governance Findings Resolution Analysis
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluator-verified status of brand violations between v{diffData.orig_version} and v{diffData.newer_version}.
              </p>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 text-xs">
              <button
                type="button"
                onClick={() => setActiveFindingTab('all')}
                className={`px-2.5 py-1 rounded-lg transition cursor-pointer ${
                  activeFindingTab === 'all'
                    ? 'bg-slate-800 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All ({diffData.resolved_findings.length + diffData.unresolved_findings.length + diffData.introduced_findings.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveFindingTab('resolved')}
                className={`px-2.5 py-1 rounded-lg transition cursor-pointer flex items-center gap-1 ${
                  activeFindingTab === 'resolved'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Resolved ({diffData.resolved_findings.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveFindingTab('unresolved')}
                className={`px-2.5 py-1 rounded-lg transition cursor-pointer flex items-center gap-1 ${
                  activeFindingTab === 'unresolved'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Unresolved ({diffData.unresolved_findings.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveFindingTab('introduced')}
                className={`px-2.5 py-1 rounded-lg transition cursor-pointer flex items-center gap-1 ${
                  activeFindingTab === 'introduced'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Introduced ({diffData.introduced_findings.length})
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {/* 1. Resolved Findings List */}
            {(activeFindingTab === 'all' || activeFindingTab === 'resolved') &&
              diffData.resolved_findings.map((f, i) => (
                <div
                  key={`res-${i}`}
                  className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/30 text-xs space-y-1.5 animate-in fade-in"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold text-[10px]">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        Resolved in v{diffData.newer_version}
                      </span>
                      {getSeverityBadge(f.severity)}
                      <span className="font-semibold text-slate-200">{f.rule_name_or_fact}</span>
                    </div>
                    {f.matched_text && (
                      <span className="text-[11px] font-mono line-through text-slate-500">
                        Original: "{f.matched_text}"
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300 text-xs">{f.explanation}</p>
                  <div className="text-[11px] text-emerald-400/90 font-medium flex items-center gap-1">
                    <span>&bull; Verified: Evaluator confirmed violation is no longer present in revision v{diffData.newer_version}.</span>
                  </div>
                </div>
              ))}

            {/* 2. Unresolved Findings List */}
            {(activeFindingTab === 'all' || activeFindingTab === 'unresolved') &&
              diffData.unresolved_findings.map((f, i) => (
                <div
                  key={`unres-${i}`}
                  className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs space-y-2 animate-in fade-in"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 font-semibold text-[10px] border border-amber-500/30">
                        <AlertTriangle className="w-3 h-3 text-amber-400" />
                        Unresolved
                      </span>
                      {getSeverityBadge(f.severity)}
                      <span className="font-semibold text-slate-200">{f.rule_name_or_fact}</span>
                    </div>
                    {f.matched_text && (
                      <span className="text-[11px] font-mono text-rose-300 bg-rose-500/10 px-2 py-0.5 rounded">
                        Active match: "{f.matched_text}"
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300 text-xs">{f.explanation}</p>
                  {f.suggested_correction && (
                    <div className="pt-2 flex items-center justify-between border-t border-slate-800/80">
                      <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <span className="font-medium text-slate-300">Suggested Fix:</span>
                        <span className="font-mono text-emerald-400 font-semibold">
                          {f.suggested_correction}
                        </span>
                      </div>
                      {onApplyFix && (
                        <button
                          type="button"
                          onClick={() => onApplyFix(f)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition cursor-pointer"
                        >
                          Apply to Editor
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}

            {/* 3. Introduced Findings List */}
            {(activeFindingTab === 'all' || activeFindingTab === 'introduced') &&
              diffData.introduced_findings.map((f, i) => (
                <div
                  key={`intro-${i}`}
                  className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/30 text-xs space-y-1.5 animate-in fade-in"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-semibold text-[10px] border border-rose-500/30">
                        <PlusCircle className="w-3 h-3 text-rose-400" />
                        Introduced in v{diffData.newer_version}
                      </span>
                      {getSeverityBadge(f.severity)}
                      <span className="font-semibold text-rose-200">{f.rule_name_or_fact}</span>
                    </div>
                    {f.matched_text && (
                      <span className="text-[11px] font-mono text-rose-300 bg-rose-500/20 px-2 py-0.5 rounded">
                        "{f.matched_text}"
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300 text-xs">{f.explanation}</p>
                  {f.suggested_correction && (
                    <div className="text-xs text-slate-400 flex items-center gap-1">
                      <span>Suggested correction:</span>
                      <span className="text-emerald-400 font-mono font-medium">{f.suggested_correction}</span>
                    </div>
                  )}
                </div>
              ))}

            {/* Empty state within category */}
            {activeFindingTab === 'resolved' && diffData.resolved_findings.length === 0 && (
              <div className="p-6 text-center text-slate-500 text-xs">
                No findings were resolved between v{diffData.orig_version} and v{diffData.newer_version}.
              </div>
            )}
            {activeFindingTab === 'unresolved' && diffData.unresolved_findings.length === 0 && (
              <div className="p-6 text-center text-emerald-400 text-xs font-semibold">
                Awesome! All violations from v{diffData.orig_version} have been resolved in v{diffData.newer_version}.
              </div>
            )}
            {activeFindingTab === 'introduced' && diffData.introduced_findings.length === 0 && (
              <div className="p-6 text-center text-slate-500 text-xs">
                No new violations were introduced in revision v{diffData.newer_version}.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
