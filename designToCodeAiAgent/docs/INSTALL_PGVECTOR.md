-- ============================================
-- Upgrade Database to Use pgvector
-- Run this after installing pgvector extension
-- ============================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector column to components table
ALTER TABLE components 
ADD COLUMN IF NOT EXISTS embedding vector(512);

-- Create vector index for similarity search
CREATE INDEX IF NOT EXISTS idx_components_embedding 
ON components USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Migrate existing JSON embeddings to vector format
-- (This will run in Phase 2 when we have actual embeddings)
UPDATE components 
SET embedding = (
    SELECT array_agg(value::float)::vector
    FROM jsonb_array_elements_text(embedding_json)
)
WHERE embedding_json IS NOT NULL 
  AND embedding IS NULL;

-- Create similarity search function
CREATE OR REPLACE FUNCTION search_similar_components(
    query_embedding vector(512),
    similarity_threshold float DEFAULT 0.7,
    max_results int DEFAULT 10
)
RETURNS TABLE (
    component_id integer,
    component_name varchar,
    component_type varchar,
    similarity_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.component_id,
        c.component_name,
        c.component_type,
        1 - (c.embedding <=> query_embedding) as similarity_score
    FROM components c
    WHERE 
        c.embedding IS NOT NULL
        AND c.is_active = true
        AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✓ pgvector upgrade complete!';
    RAISE NOTICE '✓ Added vector column to components table';
    RAISE NOTICE '✓ Created similarity search function';
    RAISE NOTICE '→ Ready for Phase 2 visual similarity matching';
END $$;

