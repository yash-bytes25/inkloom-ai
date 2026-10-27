-- ==============================================================================
-- Inkloom AI: Database Schema Migration 002
-- Row Level Security (RLS) & Multi-Tenant Access Control Policies
-- ==============================================================================

-- 1. SECURITY DEFINER HELPER FUNCTIONS

-- Returns all organisation IDs the current authenticated user belongs to
CREATE OR REPLACE FUNCTION public.current_user_org_ids()
RETURNS SETOF UUID AS $$
    SELECT org_id
    FROM public.organisation_members
    WHERE user_id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp;

-- Checks if current user holds one of the required roles in the given organisation
CREATE OR REPLACE FUNCTION public.current_user_has_role(target_org_id UUID, required_roles TEXT[])
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organisation_members
        WHERE org_id = target_org_id
          AND user_id = auth.uid()
          AND role = ANY(required_roles)
    );
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp;

-- Restrict function execution strictly to authenticated users
REVOKE EXECUTE ON FUNCTION public.current_user_org_ids() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_org_ids() TO authenticated;
REVOKE EXECUTE ON FUNCTION public.current_user_has_role(UUID, TEXT[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_has_role(UUID, TEXT[]) TO authenticated;


-- 2. ENABLE ROW LEVEL SECURITY ON ALL TABLES
ALTER TABLE public.organisations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organisation_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_guidelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prohibited_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preferred_wordings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approved_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.required_disclaimers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_content_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_decisions ENABLE ROW LEVEL SECURITY;


-- 3. ORGANISATIONS POLICIES
-- Members can view their organisation
CREATE POLICY "org_member_select" ON public.organisations
    FOR SELECT
    USING (id IN (SELECT public.current_user_org_ids()));

-- Only authenticated users creating a new org can insert
CREATE POLICY "org_auth_insert" ON public.organisations
    FOR INSERT
    WITH CHECK (auth.uid() IS NOT NULL);

-- Only owners/admins can update org metadata
CREATE POLICY "org_admin_update" ON public.organisations
    FOR UPDATE
    USING (public.current_user_has_role(id, ARRAY['owner', 'admin']));


-- 4. ORGANISATION MEMBERS POLICIES
-- Members can see other members in their organisation
CREATE POLICY "org_members_select" ON public.organisation_members
    FOR SELECT
    USING (org_id IN (SELECT public.current_user_org_ids()));

-- Only owners and admins can invite or change roles
CREATE POLICY "org_members_admin_insert" ON public.organisation_members
    FOR INSERT
    WITH CHECK (public.current_user_has_role(org_id, ARRAY['owner', 'admin']));

CREATE POLICY "org_members_admin_update" ON public.organisation_members
    FOR UPDATE
    USING (public.current_user_has_role(org_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.current_user_has_role(org_id, ARRAY['owner', 'admin']));

CREATE POLICY "org_members_admin_delete" ON public.organisation_members
    FOR DELETE
    USING (public.current_user_has_role(org_id, ARRAY['owner', 'admin']));


-- 5. BRAND GUIDELINES & RULES POLICIES
-- All members can read guidelines belonging to their organisation
CREATE POLICY "guidelines_member_select" ON public.brand_guidelines
    FOR SELECT
    USING (org_id IN (SELECT public.current_user_org_ids()));

CREATE POLICY "guidelines_admin_modify" ON public.brand_guidelines
    FOR ALL
    USING (public.current_user_has_role(org_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.current_user_has_role(org_id, ARRAY['owner', 'admin']));

-- Prohibited Terms (Inherit org scope via guideline_id)
CREATE POLICY "prohibited_terms_member_select" ON public.prohibited_terms
    FOR SELECT
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "prohibited_terms_admin_modify" ON public.prohibited_terms
    FOR ALL
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE public.current_user_has_role(org_id, ARRAY['owner', 'admin'])
    ));

-- Preferred Wordings
CREATE POLICY "preferred_wordings_member_select" ON public.preferred_wordings
    FOR SELECT
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "preferred_wordings_admin_modify" ON public.preferred_wordings
    FOR ALL
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE public.current_user_has_role(org_id, ARRAY['owner', 'admin'])
    ));

-- Approved Facts
CREATE POLICY "approved_facts_member_select" ON public.approved_facts
    FOR SELECT
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "approved_facts_admin_modify" ON public.approved_facts
    FOR ALL
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE public.current_user_has_role(org_id, ARRAY['owner', 'admin'])
    ));

-- Required Disclaimers
CREATE POLICY "required_disclaimers_member_select" ON public.required_disclaimers
    FOR SELECT
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "required_disclaimers_admin_modify" ON public.required_disclaimers
    FOR ALL
    USING (guideline_id IN (
        SELECT id FROM public.brand_guidelines WHERE public.current_user_has_role(org_id, ARRAY['owner', 'admin'])
    ));


-- 6. SUBMISSIONS & CONTENT VERSIONS POLICIES
-- Members can view submissions in their organisation
CREATE POLICY "submissions_member_select" ON public.submissions
    FOR SELECT
    USING (org_id IN (SELECT public.current_user_org_ids()));

-- Any member of the organisation can create a submission
CREATE POLICY "submissions_member_insert" ON public.submissions
    FOR INSERT
    WITH CHECK (
        org_id IN (SELECT public.current_user_org_ids())
        AND (creator_id = auth.uid() OR is_demo = true)
    );

-- Creator or admin can update a submission (only when not in_review, or transitioning to submit)
CREATE POLICY "submissions_creator_update" ON public.submissions
    FOR UPDATE
    USING (
        org_id IN (SELECT public.current_user_org_ids())
        AND (creator_id = auth.uid() OR public.current_user_has_role(org_id, ARRAY['owner', 'admin', 'reviewer']))
    )
    WITH CHECK (
        org_id IN (SELECT public.current_user_org_ids())
        AND (
            (status NOT IN ('approved', 'rejected'))
            OR public.current_user_has_role(org_id, ARRAY['owner', 'admin', 'reviewer'])
        )
        AND (
            status != 'approved'
            OR creator_id IS NULL
            OR creator_id != auth.uid()
            OR is_demo = true
        )
    );

-- Content Versions (Read by org members, written by creator or admin; strictly immutable)
CREATE POLICY "content_versions_member_select" ON public.submission_content_versions
    FOR SELECT
    USING (submission_id IN (
        SELECT id FROM public.submissions WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "content_versions_member_insert" ON public.submission_content_versions
    FOR INSERT
    WITH CHECK (submission_id IN (
        SELECT id FROM public.submissions WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "content_versions_no_update" ON public.submission_content_versions
    FOR UPDATE
    USING (false);

CREATE POLICY "content_versions_no_delete" ON public.submission_content_versions
    FOR DELETE
    USING (false);


-- 7. REVIEW FINDINGS POLICIES (Read/write by org members during audit; strictly immutable once saved)
CREATE POLICY "findings_member_select" ON public.review_findings
    FOR SELECT
    USING (submission_id IN (
        SELECT id FROM public.submissions WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "findings_member_insert" ON public.review_findings
    FOR INSERT
    WITH CHECK (submission_id IN (
        SELECT id FROM public.submissions WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

CREATE POLICY "findings_no_update" ON public.review_findings
    FOR UPDATE
    USING (false);

CREATE POLICY "findings_no_delete" ON public.review_findings
    FOR DELETE
    USING (false);


-- 8. REVIEW DECISIONS POLICIES (Enforce Reviewer Role Security & Review History Immutability)
-- Members can view decision audit history for their organisation's submissions
CREATE POLICY "decisions_member_select" ON public.review_decisions
    FOR SELECT
    USING (submission_id IN (
        SELECT id FROM public.submissions WHERE org_id IN (SELECT public.current_user_org_ids())
    ));

-- CRITICAL ROLE CHECK: Only users with 'reviewer', 'admin', or 'owner' role can record review decisions!
-- Attributed reviewer_id must match authenticated user or is_demo_reviewer flag
CREATE POLICY "decisions_reviewer_insert" ON public.review_decisions
    FOR INSERT
    WITH CHECK (
        submission_id IN (
            SELECT s.id FROM public.submissions s
            WHERE public.current_user_has_role(s.org_id, ARRAY['owner', 'admin', 'reviewer'])
              AND (decision != 'approved' OR s.creator_id IS NULL OR s.creator_id != auth.uid())
        )
        AND (reviewer_id = auth.uid() OR is_demo_reviewer = true)
    );

-- Review decisions are strictly immutable audit logs: NO UPDATE OR DELETE ALLOWED
CREATE POLICY "decisions_no_update" ON public.review_decisions
    FOR UPDATE
    USING (false);

CREATE POLICY "decisions_no_delete" ON public.review_decisions
    FOR DELETE
    USING (false);


-- 9. SCHEMA PERMISSIONS & GRANTS
-- PostgREST executes queries using the 'authenticated' or 'anon' database roles.
-- Ensure authenticated users have access to schemas and tables (governed by RLS).
GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT SELECT ON public.brand_guidelines, public.prohibited_terms, public.preferred_wordings, public.approved_facts, public.required_disclaimers TO anon;

