"""
Lookup Engine.

Resolves reference data (Equipment, Product, Recipe, Chamber, Customer,
etc.) as defined in metadata.lookup_config, with a simple per-process TTL
cache to avoid hammering Aurora on every record for slowly-changing
reference tables.
"""
import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class LookupEngine:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._cache: dict[str, tuple[float, dict[Any, Any]]] = {}

    def _load_lookup_table(self, lookup: dict) -> dict[Any, Any]:
        query = text(
            f'SELECT "{lookup["lookup_key_column"]}" AS k, "{lookup["lookup_value_column"]}" AS v '
            f'FROM "{lookup["lookup_schema"]}"."{lookup["lookup_table"]}"'
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return {row["k"]: row["v"] for row in rows}

    def _get_cached_table(self, lookup: dict) -> dict[Any, Any]:
        name = lookup["lookup_name"]
        ttl = lookup.get("cache_ttl_seconds", 300)
        now = time.monotonic()

        cached = self._cache.get(name)
        if cached and (now - cached[0]) < ttl:
            return cached[1]

        table = self._load_lookup_table(lookup)
        self._cache[name] = (now, table)
        return table

    def apply_lookups(self, record: dict, lookups: list[dict]) -> dict:
        """Enrich a record in place with all applicable lookup columns."""
        enriched = dict(record)
        for lookup in lookups:
            source_column = lookup["source_column"]
            target_column = lookup["target_column"]
            if source_column not in enriched:
                continue
            table = self._get_cached_table(lookup)
            enriched[target_column] = table.get(enriched[source_column])
        return enriched
