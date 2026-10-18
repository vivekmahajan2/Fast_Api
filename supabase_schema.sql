-- =============================================================================
-- Supabase Schema Migration: AI Career Agent
-- Run this script in your Supabase Dashboard: SQL Editor -> New Query -> Run
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. Candidate Profiles Table
-- Stores candidate background, resume text, target titles, and skills
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    target_titles TEXT[] NOT NULL DEFAULT '{}',
    primary_skills TEXT[] NOT NULL DEFAULT '{}',
    secondary_skills TEXT[] NOT NULL DEFAULT '{}',
    experience_years NUMERIC(4, 1) NOT NULL DEFAULT 0.0,
    preferred_locations TEXT[] NOT NULL DEFAULT '{}',
    workplace_preferences TEXT[] NOT NULL DEFAULT '{"remote"}',
    resume_raw_text TEXT,
    bio TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. Jobs Table
-- Stores fetched job listings with deduplication on (provider, external_job_id)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_job_id TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'jsearch',
    title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    location TEXT,
    country TEXT,
    workplace_type TEXT CHECK (workplace_type IN ('remote', 'hybrid', 'on_site', 'unspecified')) DEFAULT 'unspecified',
    experience_level TEXT CHECK (experience_level IN ('internship', 'entry_level', 'associate', 'mid_senior', 'director', 'executive', 'unspecified')) DEFAULT 'unspecified',
    description TEXT NOT NULL,
    job_url TEXT NOT NULL,
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    salary_currency TEXT DEFAULT 'USD',
    posted_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'matched', 'shortlisted', 'approved', 'applied', 'rejected', 'archived')),
    raw_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_provider_job_id UNIQUE (provider, external_job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_provider_ext_id ON jobs(provider, external_job_id);

-- -----------------------------------------------------------------------------
-- 3. Job Matches Table
-- Stores LangGraph evaluation reports, scoring breakdown, and recommendations
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    skill_match_score INTEGER NOT NULL CHECK (skill_match_score BETWEEN 0 AND 100),
    experience_match_score INTEGER NOT NULL CHECK (experience_match_score BETWEEN 0 AND 100),
    matched_skills TEXT[] DEFAULT '{}',
    missing_skills TEXT[] DEFAULT '{}',
    reasoning TEXT NOT NULL,
    tailored_pitch TEXT,
    recommended_action TEXT CHECK (recommended_action IN ('strongly_recommend', 'recommend', 'neutral', 'not_recommended')) DEFAULT 'neutral',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_job_candidate_match UNIQUE (job_id, candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_job_matches_score ON job_matches(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_matches_job_id ON job_matches(job_id);
CREATE INDEX IF NOT EXISTS idx_job_matches_candidate_id ON job_matches(candidate_id);

-- -----------------------------------------------------------------------------
-- 4. Application Approvals Table
-- Human-in-the-loop approval tracking before any external application action
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS application_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approval_notes TEXT,
    submission_status TEXT NOT NULL DEFAULT 'pending' CHECK (submission_status IN ('pending', 'submitted', 'failed', 'cancelled')),
    submitted_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_job_candidate ON application_approvals(job_id, candidate_id);

-- -----------------------------------------------------------------------------
-- 5. Updated_at Trigger Utility
-- Automatically keeps updated_at synchronized
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_update_candidate_profiles ON candidate_profiles;
CREATE TRIGGER trigger_update_candidate_profiles
    BEFORE UPDATE ON candidate_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_column();

DROP TRIGGER IF EXISTS trigger_update_jobs ON jobs;
CREATE TRIGGER trigger_update_jobs
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_column();

-- -----------------------------------------------------------------------------
-- 6. Sample Candidate Seed Data (Optional for initial testing)
-- -----------------------------------------------------------------------------
INSERT INTO candidate_profiles (
    full_name,
    email,
    target_titles,
    primary_skills,
    secondary_skills,
    experience_years,
    preferred_locations,
    workplace_preferences,
    bio
) VALUES (
    'AI Engineering Candidate',
    'candidate@example.com',
    ARRAY['AI Engineer', 'Machine Learning Engineer', 'Python Backend Developer'],
    ARRAY['Python', 'FastAPI', 'LangChain', 'LangGraph', 'Supabase', 'PostgreSQL', 'Docker'],
    ARRAY['PyTorch', 'Vector Databases', 'n8n', 'Redis', 'Git'],
    1.5,
    ARRAY['India', 'Remote'],
    ARRAY['remote', 'hybrid'],
    'AI Engineer specializing in agentic workflows, LLM orchestration, and scalable FastAPI backend services.'
) ON CONFLICT (email) DO NOTHING;
