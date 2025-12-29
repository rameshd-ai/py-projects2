-- ===========================================
-- Figma to MiBlock Component Generator
-- PostgreSQL Database Schema with pgvector
-- ===========================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables (if recreating)
DROP TABLE IF EXISTS library_refresh_tasks CASCADE;
DROP TABLE IF EXISTS generation_tasks CASCADE;
DROP TABLE IF EXISTS components CASCADE;

-- ===========================================
-- Components Table
-- Stores all library components with embeddings
-- ===========================================
CREATE TABLE components (
    -- Primary Key
    component_id SERIAL PRIMARY KEY,
    
    -- Component Info
    component_name VARCHAR(255) NOT NULL,
    component_type VARCHAR(100),
    description TEXT,
    
    -- Component Data (JSON)
    config_json JSONB NOT NULL,
    format_json JSONB NOT NULL,
    records_json JSONB NOT NULL,
    
    -- Screenshot Info
    screenshot_url VARCHAR(500),
    screenshot_path VARCHAR(500),
    screenshot_hash VARCHAR(64),  -- For quick duplicate detection
    
    -- Visual Embedding (CLIP - 512 dimensions)
    embedding vector(512),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Source Info
    source_component_id INTEGER,  -- Original CMS component ID
    source_cms_url VARCHAR(500),
    
    -- Indexing
    CONSTRAINT unique_component_name UNIQUE(component_name)
);

-- Create indexes
CREATE INDEX idx_components_name ON components(component_name);
CREATE INDEX idx_components_type ON components(component_type);
CREATE INDEX idx_components_active ON components(is_active);
CREATE INDEX idx_components_hash ON components(screenshot_hash);

-- Create pgvector index for similarity search
-- Using IVFFlat index for faster approximate nearest neighbor search
CREATE INDEX components_embedding_idx 
ON components 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Note: For better performance, train the index after inserting data:
-- VACUUM ANALYZE components;

-- ===========================================
-- Generation Tasks Table
-- Tracks component generation requests
-- ===========================================
CREATE TABLE generation_tasks (
    -- Primary Key
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Input Info
    figma_url TEXT NOT NULL,
    figma_file_id VARCHAR(100),
    figma_node_id VARCHAR(100),
    section_name VARCHAR(255),
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100
    current_step VARCHAR(100),
    
    -- Results
    matched_component_id INTEGER REFERENCES components(component_id),
    match_score FLOAT,
    is_library_match BOOLEAN DEFAULT FALSE,
    
    -- Generated Data (if new component)
    generated_config JSONB,
    generated_format JSONB,
    generated_records JSONB,
    
    -- Screenshot
    input_screenshot_path VARCHAR(500),
    generated_screenshot_path VARCHAR(500),
    similarity_score FLOAT,
    
    -- Agents Used
    agents_executed JSONB,  -- Array of agent names and times
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Error Info
    error_message TEXT,
    error_details JSONB
);

-- Create indexes
CREATE INDEX idx_generation_tasks_status ON generation_tasks(status);
CREATE INDEX idx_generation_tasks_created ON generation_tasks(created_at DESC);
CREATE INDEX idx_generation_tasks_figma_url ON generation_tasks(figma_url);

-- ===========================================
-- Library Refresh Tasks Table
-- Tracks library ingestion/refresh operations
-- ===========================================
CREATE TABLE library_refresh_tasks (
    -- Primary Key
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Task Info
    refresh_type VARCHAR(20) NOT NULL,  -- full, incremental
    status VARCHAR(50) DEFAULT 'pending',  -- pending, downloading, embedding, storing, completed, failed
    
    -- Progress Tracking
    total_components INTEGER DEFAULT 0,
    downloaded_components INTEGER DEFAULT 0,
    processed_embeddings INTEGER DEFAULT 0,
    stored_components INTEGER DEFAULT 0,
    
    -- Results
    new_components_count INTEGER DEFAULT 0,
    updated_components_count INTEGER DEFAULT 0,
    failed_components_count INTEGER DEFAULT 0,
    
    -- Current Processing
    current_component_name VARCHAR(255),
    current_phase VARCHAR(50),  -- downloading, embedding, storing
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    estimated_time_remaining INTEGER,
    
    -- Error Info
    error_message TEXT,
    failed_component_ids JSONB,
    
    -- Triggered By
    triggered_by VARCHAR(100)  -- system, user, schedule
);

-- Create indexes
CREATE INDEX idx_refresh_tasks_status ON library_refresh_tasks(status);
CREATE INDEX idx_refresh_tasks_created ON library_refresh_tasks(created_at DESC);

-- ===========================================
-- Functions
-- ===========================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_components_updated_at 
BEFORE UPDATE ON components 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to increment component usage
CREATE OR REPLACE FUNCTION increment_component_usage(comp_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE components
    SET usage_count = usage_count + 1,
        last_used_at = CURRENT_TIMESTAMP
    WHERE component_id = comp_id;
END;
$$ LANGUAGE plpgsql;

-- Function to search similar components using CLIP embeddings
CREATE OR REPLACE FUNCTION search_similar_components(
    query_embedding vector(512),
    match_threshold FLOAT DEFAULT 0.85,
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE(
    component_id INTEGER,
    component_name VARCHAR,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.component_id,
        c.component_name,
        1 - (c.embedding <=> query_embedding) AS similarity_score
    FROM components c
    WHERE c.is_active = TRUE
        AND c.embedding IS NOT NULL
        AND (1 - (c.embedding <=> query_embedding)) >= match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- ===========================================
-- Views
-- ===========================================

-- View for component statistics
CREATE OR REPLACE VIEW component_stats AS
SELECT 
    COUNT(*) as total_components,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_components,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as components_with_embeddings,
    AVG(usage_count) as avg_usage_count,
    MAX(updated_at) as last_component_update
FROM components;

-- View for recent generation tasks
CREATE OR REPLACE VIEW recent_generations AS
SELECT 
    task_id,
    figma_url,
    section_name,
    status,
    is_library_match,
    match_score,
    duration_seconds,
    created_at
FROM generation_tasks
ORDER BY created_at DESC
LIMIT 100;

-- ===========================================
-- Initial Data / Comments
-- ===========================================

COMMENT ON TABLE components IS 'Stores library components with CLIP embeddings for similarity search';
COMMENT ON COLUMN components.embedding IS '512-dimensional CLIP embedding vector for visual similarity';
COMMENT ON TABLE generation_tasks IS 'Tracks individual component generation requests from Figma';
COMMENT ON TABLE library_refresh_tasks IS 'Tracks library download and training operations';

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- ===========================================
-- Indexes for Performance
-- ===========================================

-- Additional GIN indexes for JSON searching
CREATE INDEX idx_components_config_gin ON components USING gin(config_json);
CREATE INDEX idx_components_format_gin ON components USING gin(format_json);

ANALYZE components;
ANALYZE generation_tasks;
ANALYZE library_refresh_tasks;

-- ===========================================
-- Setup Complete
-- ===========================================
SELECT 'Database setup complete!' as status;
SELECT * FROM component_stats;


