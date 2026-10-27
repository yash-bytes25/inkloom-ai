import React, { useState } from 'react'
import {
  BookOpen,
  Plus,
  Trash2,
  Edit3,
  RotateCcw,
  Save,
  Check,
  AlertCircle,
  AlertTriangle,
  Wand2,
  CheckCircle2,
  Info,
  X,
  Sparkles,
} from 'lucide-react'
import type {
  BrandRulesConfig,
  Severity,
} from '../types/governance'
import {
  validateProhibitedTerm,
  validatePreferredWording,
  validateApprovedFact,
  validateRequiredDisclaimer,
  validateFullBrandRules,
} from '../utils/guidelinesValidation'

interface BrandGuidelinesEditorProps {
  initialRules: BrandRulesConfig
  onSave: (updated: BrandRulesConfig) => Promise<void>
  onReset: () => Promise<void>
  isSaving: boolean
}

type RuleTab = 'profile' | 'prohibited' | 'preferred' | 'facts' | 'disclaimers'

export const BrandGuidelinesEditor: React.FC<BrandGuidelinesEditorProps> = ({
  initialRules,
  onSave,
  onReset,
  isSaving,
}) => {
  const [rules, setRules] = useState<BrandRulesConfig>(initialRules)
  const [activeTab, setActiveTab] = useState<RuleTab>('profile')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false)

  // Edit / Add modal state
  const [editingCategory, setEditingCategory] = useState<RuleTab | null>(null)
  const [editingItem, setEditingItem] = useState<any>(null)
  const [isNewItem, setIsNewItem] = useState<boolean>(false)
  const [modalError, setModalError] = useState<string | null>(null)

  // Sync state when initialRules reference changes from parent (e.g. after save or reset)
  const [prevInitialRules, setPrevInitialRules] = useState<BrandRulesConfig>(initialRules)
  if (prevInitialRules !== initialRules) {
    setPrevInitialRules(initialRules)
    setRules(initialRules)
  }

  // Profile field handler
  const handleProfileChange = (field: 'brand_name' | 'description' | 'voice_and_tone', value: string) => {
    setRules((prev) => ({
      ...prev,
      [field]: value,
      is_demo: false,
    }))
    setValidationError(null)
  }

  // Delete item handlers
  const handleDeleteProhibited = (id: string) => {
    setRules((prev) => ({
      ...prev,
      prohibited_terms: prev.prohibited_terms.filter((r) => r.id !== id),
      is_demo: false,
    }))
  }

  const handleDeletePreferred = (id: string) => {
    setRules((prev) => ({
      ...prev,
      preferred_wording: prev.preferred_wording.filter((r) => r.id !== id),
      is_demo: false,
    }))
  }

  const handleDeleteFact = (id: string) => {
    setRules((prev) => ({
      ...prev,
      approved_facts: prev.approved_facts.filter((f) => f.id !== id),
      is_demo: false,
    }))
  }

  const handleDeleteDisclaimer = (id: string) => {
    setRules((prev) => ({
      ...prev,
      required_disclaimers: prev.required_disclaimers.filter((d) => d.id !== id),
      is_demo: false,
    }))
  }

  // Open Add Modal
  const openAddModal = (category: RuleTab) => {
    setModalError(null)
    setIsNewItem(true)
    setEditingCategory(category)

    if (category === 'prohibited') {
      setEditingItem({
        id: `prohib-${Date.now().toString().slice(-6)}`,
        term_or_pattern: '',
        is_regex: false,
        case_sensitive: false,
        severity: 'critical' as Severity,
        explanation: '',
        suggested_replacement: '',
      })
    } else if (category === 'preferred') {
      setEditingItem({
        id: `pref-${Date.now().toString().slice(-6)}`,
        avoid_term: '',
        preferred_term: '',
        case_sensitive: false,
        severity: 'info' as Severity,
        explanation: '',
      })
    } else if (category === 'facts') {
      setEditingItem({
        id: `fact-${Date.now().toString().slice(-6)}`,
        entity: '',
        attribute: '',
        approved_value: '',
        context_keywords: '',
        conflicting_patterns: '',
        severity: 'critical' as Severity,
        explanation: '',
      })
    } else if (category === 'disclaimers') {
      setEditingItem({
        id: `disc-${Date.now().toString().slice(-6)}`,
        trigger_description: '',
        trigger_pattern: '',
        required_disclaimer_text: '',
        case_sensitive: false,
        severity: 'warning' as Severity,
        explanation: '',
      })
    }
  }

  // Open Edit Modal
  const openEditModal = (category: RuleTab, item: any) => {
    setModalError(null)
    setIsNewItem(false)
    setEditingCategory(category)

    if (category === 'facts') {
      setEditingItem({
        ...item,
        context_keywords: Array.isArray(item.context_keywords) ? item.context_keywords.join(', ') : '',
        conflicting_patterns: Array.isArray(item.conflicting_patterns) ? item.conflicting_patterns.join(', ') : '',
      })
    } else {
      setEditingItem({ ...item })
    }
  }

  // Save Modal Item
  const handleSaveModalItem = (e: React.FormEvent) => {
    e.preventDefault()
    setModalError(null)

    if (editingCategory === 'prohibited') {
      const val = validateProhibitedTerm(editingItem)
      if (!val.valid) {
        setModalError(val.error || 'Invalid prohibited term.')
        return
      }

      setRules((prev) => {
        const list = isNewItem
          ? [...prev.prohibited_terms, editingItem]
          : prev.prohibited_terms.map((r) => (r.id === editingItem.id ? editingItem : r))
        return { ...prev, prohibited_terms: list, is_demo: false }
      })
    } else if (editingCategory === 'preferred') {
      const val = validatePreferredWording(editingItem)
      if (!val.valid) {
        setModalError(val.error || 'Invalid preferred wording.')
        return
      }

      setRules((prev) => {
        const list = isNewItem
          ? [...prev.preferred_wording, editingItem]
          : prev.preferred_wording.map((r) => (r.id === editingItem.id ? editingItem : r))
        return { ...prev, preferred_wording: list, is_demo: false }
      })
    } else if (editingCategory === 'facts') {
      const val = validateApprovedFact(editingItem)
      if (!val.valid) {
        setModalError(val.error || 'Invalid approved fact.')
        return
      }

      const formattedFact = {
        ...editingItem,
        context_keywords: typeof editingItem.context_keywords === 'string'
          ? editingItem.context_keywords.split(',').map((k: string) => k.trim()).filter(Boolean)
          : Array.isArray(editingItem.context_keywords) ? editingItem.context_keywords : [],
        conflicting_patterns: typeof editingItem.conflicting_patterns === 'string'
          ? editingItem.conflicting_patterns.split(',').map((p: string) => p.trim()).filter(Boolean)
          : Array.isArray(editingItem.conflicting_patterns) ? editingItem.conflicting_patterns : [],
      }

      setRules((prev) => {
        const list = isNewItem
          ? [...prev.approved_facts, formattedFact]
          : prev.approved_facts.map((f) => (f.id === formattedFact.id ? formattedFact : f))
        return { ...prev, approved_facts: list, is_demo: false }
      })
    } else if (editingCategory === 'disclaimers') {
      const val = validateRequiredDisclaimer(editingItem)
      if (!val.valid) {
        setModalError(val.error || 'Invalid required disclaimer.')
        return
      }

      setRules((prev) => {
        const list = isNewItem
          ? [...prev.required_disclaimers, editingItem]
          : prev.required_disclaimers.map((d) => (d.id === editingItem.id ? editingItem : d))
        return { ...prev, required_disclaimers: list, is_demo: false }
      })
    }

    setEditingCategory(null)
    setEditingItem(null)
  }

  // Main Save
  const handleMainSave = async () => {
    const fullCheck = validateFullBrandRules(rules)
    if (!fullCheck.valid) {
      setValidationError(fullCheck.errors[0] || 'Brand rules validation failed.')
      return
    }

    setValidationError(null)
    try {
      await onSave(rules)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: unknown) {
      if (err instanceof Error) {
        setValidationError(err.message)
      } else {
        setValidationError('Failed to save brand guidelines.')
      }
    }
  }

  // Restore NovaSound Demo
  const handleResetDemo = async () => {
    if (window.confirm('Reset all brand guidelines to the original NovaSound Audio demo rules? Any custom rules will be replaced.')) {
      setValidationError(null)
      try {
        await onReset()
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      } catch (err: unknown) {
        if (err instanceof Error) {
          setValidationError(err.message)
        } else {
          setValidationError('Failed to reset demo rules.')
        }
      }
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Banner & Action Controls */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-emerald-400" />
              Brand Guidelines & Policy Editor
            </h2>
            <span
              className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border ${
                rules.is_demo
                  ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                  : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              }`}
            >
              {rules.is_demo ? 'NovaSound Demo Config' : 'Custom Configured Brand'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Configure approved facts, prohibited words, preferred brand tone, and disclaimers. Rule changes apply dynamically to all subsequent reviews.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={handleResetDemo}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-medium transition cursor-pointer"
            title="Restore default NovaSound demo rules"
          >
            <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
            Restore Demo
          </button>

          <button
            type="button"
            onClick={handleMainSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-semibold shadow-lg shadow-emerald-500/20 transition cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            {isSaving ? 'Saving...' : 'Save Guidelines'}
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {validationError && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}

      {saveSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2.5">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>Brand guidelines saved successfully! Active engine policy updated.</span>
        </div>
      )}

      {/* Category Tabs */}
      <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('profile')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
            activeTab === 'profile'
              ? 'bg-slate-800 text-white border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
          Identity & Voice
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('prohibited')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
            activeTab === 'prohibited'
              ? 'bg-slate-800 text-white border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
          Prohibited Terms
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-rose-500/20 text-rose-300">
            {rules.prohibited_terms.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('preferred')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
            activeTab === 'preferred'
              ? 'bg-slate-800 text-white border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Wand2 className="w-3.5 h-3.5 text-sky-400" />
          Preferred Wording
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-sky-500/20 text-sky-300">
            {rules.preferred_wording.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('facts')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
            activeTab === 'facts'
              ? 'bg-slate-800 text-white border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          Approved Facts
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300">
            {rules.approved_facts.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('disclaimers')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
            activeTab === 'disclaimers'
              ? 'bg-slate-800 text-white border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Info className="w-3.5 h-3.5 text-amber-400" />
          Disclaimers
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300">
            {rules.required_disclaimers.length}
          </span>
        </button>
      </div>

      {/* Tab 1: Brand Identity & Voice Guidance */}
      {activeTab === 'profile' && (
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              Brand Name <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              value={rules.brand_name}
              onChange={(e) => handleProfileChange('brand_name', e.target.value)}
              placeholder="e.g. Acme Audio, LuminaHealth"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Brand Positioning & Mission
            </label>
            <textarea
              rows={3}
              value={rules.description || ''}
              onChange={(e) => handleProfileChange('description', e.target.value)}
              placeholder="Brief summary of the brand's market positioning, audience, and core product lines..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 leading-relaxed"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              Brand Voice, Tone & Editorial Style
              <span className="text-[10px] text-sky-400 font-normal font-mono">(Injected into Gemini AI prompt)</span>
            </label>
            <textarea
              rows={4}
              value={rules.voice_and_tone || ''}
              onChange={(e) => handleProfileChange('voice_and_tone', e.target.value)}
              placeholder="Describe acceptable tone (e.g. authoritative, technical, warm, sophisticated) and unacceptable tones (e.g. colloquial, combative, aggressive superlatives)..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 leading-relaxed"
            />
          </div>
        </div>
      )}

      {/* Tab 2: Prohibited Terms */}
      {activeTab === 'prohibited' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Disallowed vocabulary that triggers critical or warning violations during deterministic evaluation.
            </span>
            <button
              type="button"
              onClick={() => openAddModal('prohibited')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Prohibited Term
            </button>
          </div>

          {rules.prohibited_terms.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
              No prohibited terms configured. Click "Add Prohibited Term" to add one.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {rules.prohibited_terms.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between gap-2.5"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-bold text-sm text-rose-300">
                        "{item.term_or_pattern}"
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">
                        {item.severity}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">{item.explanation}</p>

                    {item.suggested_replacement && (
                      <div className="text-xs text-slate-400">
                        Suggested replacement: <span className="text-emerald-400 font-mono">"{item.suggested_replacement}"</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono pt-1">
                      {item.is_regex && <span className="bg-slate-800 px-1.5 py-0.5 rounded">Regex Pattern</span>}
                      {item.case_sensitive && <span className="bg-slate-800 px-1.5 py-0.5 rounded">Case Sensitive</span>}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => openEditModal('prohibited', item)}
                      className="p-1 rounded text-slate-400 hover:text-slate-200 transition"
                      title="Edit rule"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteProhibited(item.id)}
                      className="p-1 rounded text-slate-400 hover:text-rose-400 transition"
                      title="Delete rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Preferred Wording */}
      {activeTab === 'preferred' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Approved terminology guidelines that suggest branded phrasing over colloquial or deprecated terms.
            </span>
            <button
              type="button"
              onClick={() => openAddModal('preferred')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 text-xs font-medium transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Preferred Wording
            </button>
          </div>

          {rules.preferred_wording.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
              No preferred wording rules configured.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {rules.preferred_wording.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between gap-2.5"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="font-mono text-slate-400 line-through">"{item.avoid_term}"</span>
                        <span className="text-slate-400">&rarr;</span>
                        <span className="font-mono font-bold text-emerald-300">"{item.preferred_term}"</span>
                      </div>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold">
                        {item.severity}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">{item.explanation}</p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => openEditModal('preferred', item)}
                      className="p-1 rounded text-slate-400 hover:text-slate-200 transition"
                      title="Edit rule"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeletePreferred(item.id)}
                      className="p-1 rounded text-slate-400 hover:text-rose-400 transition"
                      title="Delete rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Approved Facts */}
      {activeTab === 'facts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Certified technical specifications and pricing. The engine will strictly flag statements that contradict these values.
            </span>
            <button
              type="button"
              onClick={() => openAddModal('facts')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Approved Fact
            </button>
          </div>

          {rules.approved_facts.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
              No approved facts configured.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {rules.approved_facts.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between gap-2.5"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-sm text-white">
                        {item.entity}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                        {item.severity}
                      </span>
                    </div>

                    <div className="text-xs text-slate-400">
                      Attribute: <span className="text-slate-200 font-medium">{item.attribute}</span>
                    </div>

                    <div className="text-xs text-slate-400">
                      Approved Value: <span className="text-emerald-300 font-mono font-bold">{item.approved_value}</span>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">{item.explanation}</p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => openEditModal('facts', item)}
                      className="p-1 rounded text-slate-400 hover:text-slate-200 transition"
                      title="Edit rule"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteFact(item.id)}
                      className="p-1 rounded text-slate-400 hover:text-rose-400 transition"
                      title="Delete rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Required Disclaimers */}
      {activeTab === 'disclaimers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Statutory or regulatory disclaimers mandatory whenever specific marketing or guarantee triggers are detected.
            </span>
            <button
              type="button"
              onClick={() => openAddModal('disclaimers')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-medium transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Disclaimer Rule
            </button>
          </div>

          {rules.required_disclaimers.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
              No disclaimer rules configured.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {rules.required_disclaimers.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between gap-2.5"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-xs text-amber-300">
                        {item.trigger_description}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                        {item.severity}
                      </span>
                    </div>

                    <div className="text-xs text-slate-400">
                      Trigger Pattern: <code className="text-xs text-slate-300 bg-slate-950 px-1 py-0.5 rounded font-mono">{item.trigger_pattern}</code>
                    </div>

                    <div className="text-xs text-slate-400">
                      Required Disclosure:
                      <p className="text-[11px] text-slate-200 font-mono bg-slate-950 p-2 rounded mt-1 border border-slate-800">
                        {item.required_disclaimer_text}
                      </p>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">{item.explanation}</p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => openEditModal('disclaimers', item)}
                      className="p-1 rounded text-slate-400 hover:text-slate-200 transition"
                      title="Edit rule"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteDisclaimer(item.id)}
                      className="p-1 rounded text-slate-400 hover:text-rose-400 transition"
                      title="Delete rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal: Add / Edit Rule Form */}
      {editingCategory && editingItem && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-emerald-400" />
                {isNewItem ? 'Add New Rule' : 'Edit Rule'} ({editingCategory})
              </h3>
              <button
                type="button"
                onClick={() => {
                  setEditingCategory(null)
                  setEditingItem(null)
                }}
                className="p-1 text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleSaveModalItem} className="space-y-3.5 text-xs">
              {/* Category-Specific Form Fields */}
              {editingCategory === 'prohibited' && (
                <>
                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Term or Pattern <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.term_or_pattern || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, term_or_pattern: e.target.value })}
                      placeholder="e.g. cheap headphones, \\bkills the competition\\b"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
                      <input
                        type="checkbox"
                        checked={editingItem.is_regex || false}
                        onChange={(e) => setEditingItem({ ...editingItem, is_regex: e.target.checked })}
                        className="rounded border-slate-700 bg-slate-950 text-emerald-500"
                      />
                      Is Regular Expression
                    </label>

                    <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
                      <input
                        type="checkbox"
                        checked={editingItem.case_sensitive || false}
                        onChange={(e) => setEditingItem({ ...editingItem, case_sensitive: e.target.checked })}
                        className="rounded border-slate-700 bg-slate-950 text-emerald-500"
                      />
                      Case Sensitive
                    </label>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">Severity</label>
                    <select
                      value={editingItem.severity || 'critical'}
                      onChange={(e) => setEditingItem({ ...editingItem, severity: e.target.value as Severity })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    >
                      <option value="critical">Critical</option>
                      <option value="warning">Warning</option>
                      <option value="info">Info</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Explanation <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={editingItem.explanation || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, explanation: e.target.value })}
                      placeholder="Why is this term prohibited under brand guidelines?"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">Suggested Approved Replacement</label>
                    <input
                      type="text"
                      value={editingItem.suggested_replacement || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, suggested_replacement: e.target.value })}
                      placeholder="e.g. accessible high-fidelity audio"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                </>
              )}

              {editingCategory === 'preferred' && (
                <>
                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Term to Avoid <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.avoid_term || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, avoid_term: e.target.value })}
                      placeholder="e.g. earbuds, noise cancellation"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Approved/Preferred Term <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.preferred_term || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, preferred_term: e.target.value })}
                      placeholder="e.g. in-ear acoustic monitors, Active Acoustic Isolation™"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">Severity</label>
                    <select
                      value={editingItem.severity || 'info'}
                      onChange={(e) => setEditingItem({ ...editingItem, severity: e.target.value as Severity })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    >
                      <option value="info">Info (Style)</option>
                      <option value="warning">Warning</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Explanation <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={editingItem.explanation || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, explanation: e.target.value })}
                      placeholder="Brand voice guidance on why preferred term is required."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                </>
              )}

              {editingCategory === 'facts' && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="font-semibold text-slate-300">
                        Target Entity <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={editingItem.entity || ''}
                        onChange={(e) => setEditingItem({ ...editingItem, entity: e.target.value })}
                        placeholder="e.g. NovaSound Apex Wireless"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-semibold text-slate-300">
                        Attribute <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={editingItem.attribute || ''}
                        onChange={(e) => setEditingItem({ ...editingItem, attribute: e.target.value })}
                        placeholder="e.g. MSRP Price, Battery Playback"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Approved Value <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.approved_value || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, approved_value: e.target.value })}
                      placeholder="e.g. $299, 40 hours, IPX7 rating"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Context Keywords <span className="text-slate-400 font-normal">(comma-separated)</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.context_keywords || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, context_keywords: e.target.value })}
                      placeholder="price, cost, msrp, $"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Conflicting / Contradictory Patterns <span className="text-slate-400 font-normal">(comma-separated regex)</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.conflicting_patterns || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, conflicting_patterns: e.target.value })}
                      placeholder="\\$(?!299\\b)\\d+, \\$199"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Explanation <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={editingItem.explanation || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, explanation: e.target.value })}
                      placeholder="Certified specification reference."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                </>
              )}

              {editingCategory === 'disclaimers' && (
                <>
                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Condition / Description <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.trigger_description || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, trigger_description: e.target.value })}
                      placeholder="e.g. Mentions lifetime warranty or indefinite guarantee"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Trigger Pattern <span className="text-rose-400">*</span> <span className="text-slate-400 font-normal">(regex)</span>
                    </label>
                    <input
                      type="text"
                      value={editingItem.trigger_pattern || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, trigger_pattern: e.target.value })}
                      placeholder="e.g. \\b(?:lifetime\\s+warranty|guaranteed\\s+forever)\\b"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:border-emerald-500 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Mandatory Disclaimer Text <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={editingItem.required_disclaimer_text || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, required_disclaimer_text: e.target.value })}
                      placeholder="*Subject to NovaSound Limited Lifetime Warranty Terms and fair usage policy."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:border-emerald-500 focus:outline-none font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-slate-300">
                      Regulatory Rationale <span className="text-rose-400">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={editingItem.explanation || ''}
                      onChange={(e) => setEditingItem({ ...editingItem, explanation: e.target.value })}
                      placeholder="Why is this disclosure required?"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                </>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setEditingCategory(null)
                    setEditingItem(null)
                  }}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold shadow-md transition"
                >
                  Save Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
