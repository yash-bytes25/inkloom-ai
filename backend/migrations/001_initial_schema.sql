-- ==============================================================================
-- Inkloom AI: Database Schema Migration 001
-- Multi-Tenant Brand Governance & Content Policy Auditor
-- ==============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. ORGANISATIONS
CREATE TABLE IF NOT EXISTS public.organisations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. ORGANISATION MEMBERS & ROLES
-- Roles: 'owner', 'admin', 'reviewer', 'creator'
CREATE TABLE IF NOT EXISTS public.organisation_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organisations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'reviewer', 'creator')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, user_id)
);

-- 3. BRAND GUIDELINES (Versioned sets of brand rules)
CREATE TABLE IF NOT EXISTS public.brand_guidelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organisations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. PROHIBITED TERMS
CREATE TABLE IF NOT EXISTS public.prohibited_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guideline_id UUID NOT NULL REFERENCES public.brand_guidelines(id) ON DELETE CASCADE,
    term_or_pattern TEXT NOT NULL,
    is_regex BOOLEAN NOT NULL DEFAULT false,
    case_sensitive BOOLEAN NOT NULL DEFAULT false,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    explanation TEXT NOT NULL,
    suggested_replacement TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. PREFERRED WORDINGS (Brand Nomenclature)
CREATE TABLE IF NOT EXISTS public.preferred_wordings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guideline_id UUID NOT NULL REFERENCES public.brand_guidelines(id) ON DELETE CASCADE,
    avoid_term TEXT NOT NULL,
    preferred_term TEXT NOT NULL,
    case_sensitive BOOLEAN NOT NULL DEFAULT false,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    explanation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. APPROVED FACTS (Certified brand specs and claims)
CREATE TABLE IF NOT EXISTS public.approved_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guideline_id UUID NOT NULL REFERENCES public.brand_guidelines(id) ON DELETE CASCADE,
    entity TEXT NOT NULL,
    attribute TEXT NOT NULL,
    approved_value TEXT NOT NULL,
    context_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    conflicting_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    explanation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. REQUIRED DISCLAIMERS
CREATE TABLE IF NOT EXISTS public.required_disclaimers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guideline_id UUID NOT NULL REFERENCES public.brand_guidelines(id) ON DELETE CASCADE,
    trigger_pattern TEXT NOT NULL,
    trigger_description TEXT NOT NULL,
    required_disclaimer_text TEXT NOT NULL,
    case_sensitive BOOLEAN NOT NULL DEFAULT false,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    explanation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. CONTENT SUBMISSIONS (State machine root)
CREATE TABLE IF NOT EXISTS public.submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organisations(id) ON DELETE CASCADE,
    guideline_id UUID REFERENCES public.brand_guidelines(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    current_version INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('draft', 'in_review', 'changes_requested', 'approved', 'rejected')),
    creator_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    creator_name TEXT NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT false,
    submitted_at TIMESTAMPTZ,
    submitted_content_snapshot TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. SUBMISSION CONTENT VERSIONS (Immutable historical snapshots)
CREATE TABLE IF NOT EXISTS public.submission_content_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    version INT NOT NULL,
    content TEXT NOT NULL,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (submission_id, version)
);

-- 10. REVIEW FINDINGS (Audit issues tied to specific version)
CREATE TABLE IF NOT EXISTS public.review_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    content_version INT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    matched_text TEXT,
    start_index INT,
    end_index INT,
    explanation TEXT NOT NULL,
    rule_name_or_fact TEXT NOT NULL,
    suggested_correction TEXT,
    evidence_status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'deterministic',
    confidence NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. REVIEW DECISIONS (Immutable reviewer audit log)
CREATE TABLE IF NOT EXISTS public.review_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'changes_requested', 'rejected')),
    reviewer_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    reviewer_name TEXT NOT NULL,
    is_demo_reviewer BOOLEAN NOT NULL DEFAULT false,
    comment TEXT,
    content_version INT NOT NULL,
    content_snapshot TEXT NOT NULL,
    findings_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    guideline_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==============================================================================
-- INDEXES FOR PERFORMANCE AND ISOLATION
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_org_members_user ON public.organisation_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON public.organisation_members(org_id);
CREATE INDEX IF NOT EXISTS idx_guidelines_org ON public.brand_guidelines(org_id);
CREATE INDEX IF NOT EXISTS idx_submissions_org ON public.submissions(org_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON public.submissions(status);
CREATE INDEX IF NOT EXISTS idx_content_versions_sub ON public.submission_content_versions(submission_id, version);
CREATE INDEX IF NOT EXISTS idx_findings_sub_version ON public.review_findings(submission_id, content_version);
CREATE INDEX IF NOT EXISTS idx_decisions_sub ON public.review_decisions(submission_id);
