import asyncio
from src.graph.client import Neo4jClient

async def repair():
    client = Neo4jClient()
    await client.connect()

    # 1. Ensure all intermediate directories exist
    files = await client.execute_query(
        "MATCH (f:File) RETURN f.repo_id as repo_id, f.file_path as path, f.commit_sha as commit_sha, f.branch as branch"
    )
    all_dirs = set()
    for f in files:
        repo_id = f["repo_id"]
        path = f["path"]
        parts = path.split("/")
        if len(parts) > 1:
            curr = ""
            for p in parts[:-1]:
                curr = f"{curr}/{p}" if curr else p
                all_dirs.add((repo_id, curr, f.get("commit_sha") or "unknown", f.get("branch") or "main"))

    print(f"Total directories to ensure across all repos: {len(all_dirs)}")
    batch = [
        {
            "uid": f"dir:{repo_id}:{d}",
            "path": d,
            "name": d.split("/")[-1],
            "depth": len(d.split("/")),
            "repo_id": repo_id,
            "commit_sha": sha,
            "branch": br,
        }
        for repo_id, d, sha, br in all_dirs
    ]

    await client.execute_query(
        """
        UNWIND $batch AS item
        MERGE (d:Directory {uid: item.uid})
        SET d.path = item.path,
            d.name = item.name,
            d.depth = item.depth,
            d.repo_id = item.repo_id,
            d.commit_sha = item.commit_sha,
            d.branch = item.branch
        """,
        {"batch": batch},
    )

    # 2. Delete ALL existing CONTAINS edges to rebuild cleanly and strictly hierarchically
    del_res = await client.execute_query("MATCH ()-[r:CONTAINS]->() DELETE r RETURN count(r) as c")
    print(f"Deleted old CONTAINS edges: {del_res[0]['c']}")

    # 3. Wire Repository -> Root Directory
    w1 = await client.execute_query(
        """
        MATCH (d:Directory)
        WHERE NOT d.path CONTAINS '/'
        MATCH (r:Repository)
        WHERE toLower(r.repo_id) = toLower(d.repo_id)
        MERGE (r)-[rel:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0}]->(d)
        SET rel.repo_id = d.repo_id
        RETURN count(rel) as c
        """
    )
    print(f"Repository -> Root Directory edges created: {w1[0]['c']}")

    # 4. Wire Directory -> Subdirectory
    w2 = await client.execute_query(
        """
        MATCH (child:Directory)
        WHERE child.path CONTAINS '/'
        WITH child, substring(child.path, 0, size(child.path) - size(split(child.path, '/')[-1]) - 1) AS parent_path
        MATCH (parent:Directory {repo_id: child.repo_id, path: parent_path})
        MERGE (parent)-[rel:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0}]->(child)
        SET rel.repo_id = child.repo_id
        RETURN count(rel) as c
        """
    )
    print(f"Directory -> Subdirectory edges created: {w2[0]['c']}")

    # 5. Wire Repository -> Root File
    w3 = await client.execute_query(
        """
        MATCH (f:File)
        WHERE NOT f.file_path CONTAINS '/'
        MATCH (r:Repository)
        WHERE toLower(r.repo_id) = toLower(f.repo_id)
        MERGE (r)-[rel:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0}]->(f)
        SET rel.repo_id = f.repo_id
        RETURN count(rel) as c
        """
    )
    print(f"Repository -> Root File edges created: {w3[0]['c']}")

    # 6. Wire Directory -> File
    w4 = await client.execute_query(
        """
        MATCH (f:File)
        WHERE f.file_path CONTAINS '/'
        WITH f, substring(f.file_path, 0, size(f.file_path) - size(split(f.file_path, '/')[-1]) - 1) AS parent_path
        MATCH (d:Directory {repo_id: f.repo_id, path: parent_path})
        MERGE (d)-[rel:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0}]->(f)
        SET rel.repo_id = f.repo_id
        RETURN count(rel) as c
        """
    )
    print(f"Directory -> File edges created: {w4[0]['c']}")

    # Check nodejs-backend-template specifically
    test_res = await client.execute_query(
        """
        MATCH (src)-[r:CONTAINS]->(dst)
        WHERE toLower(src.repo_id) = toLower('AryanRacha/nodejs-backend-template')
        RETURN labels(src)[0] AS srcType, labels(dst)[0] AS dstType, count(r) AS count
        """
    )
    print("nodejs-backend-template breakdown:", test_res)

    await client.close()

if __name__ == "__main__":
    asyncio.run(repair())
