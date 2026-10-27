-- ==============================================================================
-- Inkloom AI: Database Schema Migration 003
-- Brand Guidelines Enhancements: Description and Voice & Tone Guidance
-- ==============================================================================

-- Add brand description and voice & tone guidance columns to brand_guidelines table
ALTER TABLE public.brand_guidelines
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS voice_and_tone TEXT;

-- Comment for schema documentation
COMMENT ON COLUMN public.brand_guidelines.description IS 'High-level brand identity and purpose summary';
COMMENT ON COLUMN public.brand_guidelines.voice_and_tone IS 'Specific editorial guidance on brand voice, tone, personality, and style attributes';
