from src.graph.client import Neo4jClient


async def ensure_schema(client: Neo4jClient) -> None:
    """Create constraints and indexes for strict multi-repo data isolation."""

    # Uniqueness constraint for Symbol nodes scoped by repo_id, branch, and qualified_name
    symbol_constraint = """
    CREATE CONSTRAINT symbol_repo_isolation IF NOT EXISTS
    FOR (s:Symbol)
    REQUIRE (s.repo_id, s.branch, s.qualified_name) IS UNIQUE
    """

    # Uniqueness constraint for File nodes scoped by repo_id, branch, and file_path
    file_constraint = """
    CREATE CONSTRAINT file_repo_isolation IF NOT EXISTS
    FOR (f:File)
    REQUIRE (f.repo_id, f.branch, f.file_path) IS UNIQUE
    """

    # Uniqueness constraint for Module nodes (backward compatibility)
    module_constraint = """
    CREATE CONSTRAINT module_repo_isolation IF NOT EXISTS
    FOR (m:Module)
    REQUIRE (m.repo_id, m.branch, m.file_path) IS UNIQUE
    """

    # Lookup indexes
    symbol_repo_idx = """
    CREATE INDEX symbol_repo_idx IF NOT EXISTS
    FOR (s:Symbol)
    ON (s.repo_id, s.branch)
    """

    file_repo_idx = """
    CREATE INDEX file_repo_idx IF NOT EXISTS
    FOR (f:File)
    ON (f.repo_id, f.branch)
    """

    await client.execute_query(symbol_constraint)
    await client.execute_query(file_constraint)
    await client.execute_query(module_constraint)
    await client.execute_query(symbol_repo_idx)
    await client.execute_query(file_repo_idx)
