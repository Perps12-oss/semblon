"""Schema 9 registry tables remain; schema 10 adds observations/evidence."""

from __future__ import annotations

import sqlite3

import pytest

from semblon.store import SCHEMA_VERSION, apply_migrations, connect, init_db


def test_schema_includes_nine_and_ten(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        assert SCHEMA_VERSION == "12"
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert ver == "12"
        versions = {
            int(r[0])
            for r in conn.execute("SELECT version FROM schema_migrations")
        }
        assert {8, 9, 10, 11, 12} <= versions
    finally:
        conn.close()


def test_schema_9_tables_present(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "brain_capabilities" in tables
        assert "brain_benchmarks" in tables
    finally:
        conn.close()


def test_migrate_from_schema_8_to_current(tmp_path):
    """Stamp an 8-store, drop brain tables, then roll forward through 9 and 10."""
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        for table in (
            "brain_edges",
            "brain_nodes",
            "brain_evidence",
            "brain_observations",
            "brain_capabilities",
            "brain_benchmarks",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("DELETE FROM schema_migrations WHERE version>=9")
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '8')"
        )
        conn.commit()
        assert apply_migrations(conn) == 12
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "brain_capabilities" in tables
        assert "brain_observations" in tables
        assert "brain_nodes" in tables
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert ver == "12"
    finally:
        conn.close()


def test_capability_unique_and_benchmark_fk(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        conn.execute(
            """INSERT INTO brain_benchmarks(
                 capability_id, provider_name, sample_hash, coverage,
                 cost_class, regressions_found, run_at)
               VALUES ('C7','fixture','abc',-1.0,'free',0,'t')"""
        )
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO brain_capabilities(
                 capability_id, provider_name, provider_kind, cost_class,
                 benchmark_run_id, adopted)
               VALUES ('C7','fixture','existing','free',?,0)""",
            (bid,),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO brain_capabilities(
                     capability_id, provider_name, provider_kind, cost_class, adopted)
                   VALUES ('C7','fixture','existing','free',0)"""
            )
    finally:
        conn.close()
