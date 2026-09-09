-- Supabase pgvector migration for AI Service Knowledge Base
-- Run this SQL once in your Supabase project SQL editor.
-- Replace :DIMENSION with the embedding dimension you are using:
--   gemini-embedding-001  -> 3072
--   text-embedding-3-small -> 1536
--   text-embedding-3-large -> 3072
--   bge-small-en-v1.5 (fastembed) -> 384

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the knowledge_base table
--    Change the vector dimension to match your chosen EMBEDDER.
CREATE TABLE IF NOT EXISTS knowledge_base (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    embedding   VECTOR(3072),   -- change dimension here to match your EMBEDDER
    metadata    JSONB DEFAULT '{}'
);

-- 3. Vector similarity index (IVFFlat -- good for up to ~1M rows)
CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
    ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 4. Metadata JSONB index for fast filter queries
CREATE INDEX IF NOT EXISTS knowledge_base_metadata_idx
    ON knowledge_base USING gin (metadata);

-- 5. RPC: match_documents -- semantic similarity search with optional metadata filter
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR,
    match_count     INT,
    filter          JSONB DEFAULT '{}',
    table_name      TEXT DEFAULT 'knowledge_base'
)
RETURNS TABLE (
    id         TEXT,
    content    TEXT,
    metadata   JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE FORMAT(
        'SELECT id, content, metadata,
                1 - (embedding <=> $1) AS similarity
         FROM %I
         WHERE ($2 = ''{}'' OR metadata @> $2)
         ORDER BY embedding <=> $1
         LIMIT $3',
        table_name
    ) USING query_embedding, filter, match_count;
END;
$$;

-- 6. RPC: delete_documents -- delete by metadata filter
CREATE OR REPLACE FUNCTION delete_documents(
    filter     JSONB DEFAULT '{}',
    table_name TEXT DEFAULT 'knowledge_base'
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE FORMAT(
        'DELETE FROM %I WHERE ($1 = ''{}'' OR metadata @> $1)',
        table_name
    ) USING filter;
END;
$$;

-- 7. RPC: get_documents -- retrieve by metadata filter (no vector needed)
CREATE OR REPLACE FUNCTION get_documents(
    filter     JSONB DEFAULT '{}',
    table_name TEXT DEFAULT 'knowledge_base'
)
RETURNS TABLE (id TEXT, content TEXT, metadata JSONB)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE FORMAT(
        'SELECT id, content, metadata FROM %I
         WHERE ($1 = ''{}'' OR metadata @> $1)',
        table_name
    ) USING filter;
END;
$$;

-- 8. RPC: get_vector_dimension -- used by SupabaseStore to validate dimension at startup
CREATE OR REPLACE FUNCTION get_vector_dimension(table_name TEXT)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    dim INT;
BEGIN
    SELECT (a.atttypmod - 4)
    INTO dim
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    WHERE c.relname = table_name
      AND a.attname = 'embedding'
      AND a.attnum > 0;
    RETURN dim;
END;
$$;
