"""
Load Engine.

Loads curated records into Aurora PostgreSQL target tables according to
metadata.load_config: APPEND, MERGE/UPSERT, SCD Type 1, and SCD Type 2.
Business keys and SCD columns are entirely metadata-driven.
"""
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class LoadEngine:
    def __init__(self, engine: Engine, target_schema: str):
        self.engine = engine
        self.target_schema = target_schema

    def load(self, records: list[dict[str, Any]], load_config: dict) -> int:
        if not records:
            return 0

        load_type = load_config.get("load_type", "APPEND").upper()
        table = load_config["target_table"]

        if load_type == "APPEND":
            return self._append(records, table)
        elif load_type in ("MERGE", "UPSERT"):
            business_keys = [c.strip() for c in load_config["business_key_columns"].split(",")]
            return self._upsert(records, table, business_keys)
        elif load_type == "SCD1":
            business_keys = [c.strip() for c in load_config["business_key_columns"].split(",")]
            return self._upsert(records, table, business_keys)  # SCD1 overwrites in place, same as upsert
        elif load_type == "SCD2":
            business_keys = [c.strip() for c in load_config["business_key_columns"].split(",")]
            return self._scd2(records, table, business_keys, load_config)
        else:
            raise ValueError(f"Unsupported load_type '{load_type}'")

    def _append(self, records: list[dict], table: str) -> int:
        columns = list(records[0].keys())
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        stmt = text(f'INSERT INTO "{self.target_schema}"."{table}" ({col_list}) VALUES ({placeholders})')
        with self.engine.begin() as conn:
            conn.execute(stmt, records)
        return len(records)

    def _upsert(self, records: list[dict], table: str, business_keys: list[str]) -> int:
        columns = list(records[0].keys())
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        conflict_cols = ", ".join(f'"{c}"' for c in business_keys)
        update_set = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in business_keys)

        stmt = text(f"""
            INSERT INTO "{self.target_schema}"."{table}" ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols})
            DO UPDATE SET {update_set}
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, records)
        return len(records)

    def _scd2(self, records: list[dict], table: str, business_keys: list[str], load_config: dict) -> int:
        effective_col = load_config.get("scd2_effective_column", "effective_start_date")
        expiry_col = load_config.get("scd2_expiry_column", "effective_end_date")
        current_flag_col = load_config.get("scd2_current_flag_column", "is_current")
        key_predicate = " AND ".join(f'"{c}" = :{c}' for c in business_keys)

        with self.engine.begin() as conn:
            for record in records:
                # Expire the current row for this business key, if one exists.
                conn.execute(
                    text(f"""
                        UPDATE "{self.target_schema}"."{table}"
                        SET "{expiry_col}" = now(), "{current_flag_col}" = FALSE
                        WHERE {key_predicate} AND "{current_flag_col}" = TRUE
                    """),
                    {k: record[k] for k in business_keys},
                )
                # Insert the new current version.
                insert_record = dict(record)
                insert_record[current_flag_col] = True
                columns = list(insert_record.keys())
                col_list = ", ".join(f'"{c}"' for c in columns)
                placeholders = ", ".join(f":{c}" for c in columns)
                conn.execute(
                    text(f'INSERT INTO "{self.target_schema}"."{table}" ({col_list}, "{effective_col}") '
                         f'VALUES ({placeholders}, now())'),
                    insert_record,
                )
        return len(records)
