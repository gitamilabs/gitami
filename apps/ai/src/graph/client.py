import asyncio
import logging
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from src.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j database client wrapper."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri or settings.neo4j_uri or "bolt://localhost:7687"
        self.user = user or settings.neo4j_user or "neo4j"
        self.password = password or settings.neo4j_password or "gitamipassword"
        self.database = database or settings.neo4j_database or "neo4j"
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        if not self._driver:
            config_kwargs: Dict[str, Any] = {}
            try:
                from neo4j import NotificationDisabledClassification
                config_kwargs["notifications_disabled_classifications"] = [
                    NotificationDisabledClassification.UNRECOGNIZED
                ]
            except (ImportError, AttributeError):
                pass

            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=10.0,
                connection_acquisition_timeout=15.0,
                max_connection_lifetime=300,
                **config_kwargs,
            )

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def verify_connectivity(self) -> bool:
        if not self._driver:
            await self.connect()
        assert self._driver is not None
        await asyncio.wait_for(self._driver.verify_connectivity(), timeout=10.0)
        return True

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        timeout: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Run a query asynchronously with retries and return matching record dictionaries."""
        for attempt in range(retries):
            try:
                if not self._driver:
                    await self.connect()
                assert self._driver is not None

                records, summary, keys = await asyncio.wait_for(
                    self._driver.execute_query(
                        query,
                        parameters_=(parameters or {}),
                        database_=self.database,
                    ),
                    timeout=timeout,
                )
                return [record.data() for record in records]
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = 1.0 * (2 ** attempt)
                    logger.warning(f"Neo4j execute_query attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Neo4j execute_query final attempt failed: {e}")
                    raise
        return []
