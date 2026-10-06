-- Initialize PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create indexes for better performance
-- These will be used after tables are created by Alembic

-- Set timezone
SET timezone = 'Asia/Dhaka';

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'PostGIS extension initialized successfully';
END $$;
