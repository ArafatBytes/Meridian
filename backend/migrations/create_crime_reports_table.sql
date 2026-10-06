-- Drop existing table if it exists
DROP TABLE IF EXISTS crime_reports CASCADE;

-- Create crime_category enum type
DO $$ BEGIN
    CREATE TYPE crime_category AS ENUM (
        'theft',
        'assault',
        'harassment',
        'vandalism',
        'burglary',
        'robbery',
        'fraud',
        'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create crime_reports table
CREATE TABLE IF NOT EXISTS crime_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    category crime_category NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    incident_date_time TIMESTAMP NOT NULL,
    latitude VARCHAR NOT NULL,
    longitude VARCHAR NOT NULL,
    location_name VARCHAR,
    status VARCHAR DEFAULT 'pending',
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_crime_reports_user_id ON crime_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_crime_reports_category ON crime_reports(category);
CREATE INDEX IF NOT EXISTS idx_crime_reports_incident_date_time ON crime_reports(incident_date_time);
CREATE INDEX IF NOT EXISTS idx_crime_reports_created_at ON crime_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_crime_reports_status ON crime_reports(status);

-- Create trigger for updating updated_at timestamp
CREATE OR REPLACE FUNCTION update_crime_reports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_crime_reports_updated_at ON crime_reports;
CREATE TRIGGER trigger_update_crime_reports_updated_at
    BEFORE UPDATE ON crime_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_crime_reports_updated_at();

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Crime reports table created successfully';
END $$;
