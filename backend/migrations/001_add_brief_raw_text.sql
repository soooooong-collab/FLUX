-- Migration: Add brief_raw_text column to projects table
-- For storing full text extracted from uploaded PDF briefs
-- Run: docker exec fluxv01-postgres-1 psql -U flux -d flux -f /migrations/001_add_brief_raw_text.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'projects' AND column_name = 'brief_raw_text'
    ) THEN
        ALTER TABLE projects ADD COLUMN brief_raw_text TEXT;
        RAISE NOTICE 'Added brief_raw_text column to projects table';
    ELSE
        RAISE NOTICE 'Column brief_raw_text already exists, skipping';
    END IF;
END
$$;
