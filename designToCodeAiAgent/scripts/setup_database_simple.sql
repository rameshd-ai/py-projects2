-- ============================================
-- Simple Database Schema (Without pgvector)
-- Phase 1: Foundation Setup
-- ============================================

-- Note: pgvector will be added in Phase 2
-- For now, we'll store embeddings as JSON arrays

-- ============================================
-- Table: components
-- Stores library component metadata and formats
-- ============================================
CREATE TABLE IF NOT EXISTS components (
    component_id SERIAL PRIMARY KEY,
    component_name VARCHAR(255) NOT NULL,
    component_type VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Component JSON data
    config_json JSONB NOT NULL,
    format_json JSONB NOT NULL,
    records_json JSONB NOT NULL,
    
    -- Visual comparison data
    screenshot_url VARCHAR(500),
    screenshot_path VARCHAR(500),
    embedding_json JSONB,  -- Store as JSON for now, will convert to vector later
    
    -- Metadata
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    
    -- Indexes
    UNIQUE(component_name, version)
);

-- Index for active components
CREATE INDEX IF NOT EXISTS idx_components_active 
ON components(is_active) WHERE is_active = true;

-- Index for component type
CREATE INDEX IF NOT EXISTS idx_components_type 
ON components(component_type);

-- Index for component name search
CREATE INDEX IF NOT EXISTS idx_components_name 
ON components(component_name);

-- GIN index for JSONB searching
CREATE INDEX IF NOT EXISTS idx_components_config 
ON components USING GIN(config_json);

CREATE INDEX IF NOT EXISTS idx_components_format 
ON components USING GIN(format_json);

-- ============================================
-- Table: generation_tasks
-- Tracks component generation requests
-- ============================================
CREATE TABLE IF NOT EXISTS generation_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Input
    figma_url VARCHAR(500) NOT NULL,
    figma_node_id VARCHAR(255),
    figma_screenshot_url VARCHAR(500),
    
    -- Matched component (if found)
    matched_component_id INTEGER REFERENCES components(component_id),
    match_confidence DECIMAL(5,4),  -- 0.0000 to 1.0000
    match_method VARCHAR(50),  -- 'visual_similarity', 'semantic', etc.
    
    -- Processing
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    current_agent VARCHAR(100),
    progress_percent INTEGER DEFAULT 0,
    
    -- Generated outputs
    html_content TEXT,
    format_content TEXT,
    component_definition JSONB,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Metadata
    created_by VARCHAR(100),
    metadata JSONB
);

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_generation_tasks_status 
ON generation_tasks(status);

-- Index for user queries
CREATE INDEX IF NOT EXISTS idx_generation_tasks_user 
ON generation_tasks(created_by);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_generation_tasks_created 
ON generation_tasks(created_at DESC);

-- ============================================
-- Table: library_refresh_tasks
-- Tracks library ingestion/refresh operations
-- ============================================
CREATE TABLE IF NOT EXISTS library_refresh_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Task configuration
    refresh_mode VARCHAR(20) NOT NULL,  -- 'full' or 'incremental'
    
    -- Progress tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_components INTEGER DEFAULT 0,
    processed_components INTEGER DEFAULT 0,
    failed_components INTEGER DEFAULT 0,
    
    -- Results
    new_components INTEGER DEFAULT 0,
    updated_components INTEGER DEFAULT 0,
    deleted_components INTEGER DEFAULT 0,
    
    -- Error handling
    error_message TEXT,
    error_details JSONB,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Metadata
    triggered_by VARCHAR(100),
    metadata JSONB
);

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_library_refresh_status 
ON library_refresh_tasks(status);

-- Index for date queries
CREATE INDEX IF NOT EXISTS idx_library_refresh_created 
ON library_refresh_tasks(created_at DESC);

-- ============================================
-- View: component_stats
-- Provides quick statistics on components
-- ============================================
CREATE OR REPLACE VIEW component_stats AS
SELECT 
    COUNT(*) as total_components,
    COUNT(*) FILTER (WHERE is_active = true) as active_components,
    COUNT(*) FILTER (WHERE is_active = false) as inactive_components,
    COUNT(DISTINCT component_type) as unique_types,
    MAX(updated_at) as last_update,
    COUNT(*) FILTER (WHERE screenshot_url IS NOT NULL) as with_screenshots,
    COUNT(*) FILTER (WHERE embedding_json IS NOT NULL) as with_embeddings
FROM components;

-- ============================================
-- View: recent_tasks
-- Shows recent generation tasks
-- ============================================
CREATE OR REPLACE VIEW recent_tasks AS
SELECT 
    task_id,
    figma_url,
    status,
    current_agent,
    progress_percent,
    matched_component_id,
    match_confidence,
    created_at,
    completed_at,
    EXTRACT(EPOCH FROM (COALESCE(completed_at, CURRENT_TIMESTAMP) - created_at)) as duration_seconds
FROM generation_tasks
ORDER BY created_at DESC
LIMIT 100;

-- ============================================
-- Function: search_components_by_name
-- Simple text search for components
-- ============================================
CREATE OR REPLACE FUNCTION search_components_by_name(search_term VARCHAR)
RETURNS TABLE (
    component_id INTEGER,
    component_name VARCHAR,
    component_type VARCHAR,
    description TEXT,
    similarity REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.component_id,
        c.component_name,
        c.component_type,
        c.description,
        (
            CASE 
                WHEN c.component_name ILIKE search_term || '%' THEN 1.0
                WHEN c.component_name ILIKE '%' || search_term || '%' THEN 0.8
                WHEN c.description ILIKE '%' || search_term || '%' THEN 0.6
                ELSE 0.5
            END
        )::REAL as similarity
    FROM components c
    WHERE 
        c.is_active = true
        AND (
            c.component_name ILIKE '%' || search_term || '%'
            OR c.description ILIKE '%' || search_term || '%'
        )
    ORDER BY similarity DESC, c.component_name
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Function: get_component_details
-- Get full component details including all JSON
-- ============================================
CREATE OR REPLACE FUNCTION get_component_details(comp_id INTEGER)
RETURNS TABLE (
    component_id INTEGER,
    component_name VARCHAR,
    component_type VARCHAR,
    description TEXT,
    config_json JSONB,
    format_json JSONB,
    records_json JSONB,
    screenshot_url VARCHAR,
    version INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.component_id,
        c.component_name,
        c.component_type,
        c.description,
        c.config_json,
        c.format_json,
        c.records_json,
        c.screenshot_url,
        c.version,
        c.created_at,
        c.updated_at
    FROM components c
    WHERE c.component_id = comp_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Triggers: Auto-update timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_components_updated_at
    BEFORE UPDATE ON components
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Grant permissions
-- ============================================
-- Grant all privileges to postgres user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- ============================================
-- Success message
-- ============================================
DO $$
BEGIN
    RAISE NOTICE '✓ Database schema created successfully (Simple version without pgvector)';
    RAISE NOTICE '✓ Created 3 tables: components, generation_tasks, library_refresh_tasks';
    RAISE NOTICE '✓ Created 2 views: component_stats, recent_tasks';
    RAISE NOTICE '✓ Created 2 functions: search_components_by_name, get_component_details';
    RAISE NOTICE '→ pgvector will be added in Phase 2 for visual similarity';
END $$;


