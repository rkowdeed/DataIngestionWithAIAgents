import os

os.environ.setdefault("AGENTS_ENABLED", "false")  # keep tests offline / no LLM calls

from etl_platform.agents.error_classification_agent import ErrorClassificationAgent


def test_heuristic_classifies_schema_errors():
    agent = ErrorClassificationAgent()
    assert agent.classify_heuristic("'lot' is a required property") == "SCHEMA"


def test_heuristic_classifies_range_errors():
    agent = ErrorClassificationAgent()
    assert agent.classify_heuristic("Validation failed: range check out of bounds") == "VALIDATION"


def test_heuristic_classifies_load_errors():
    agent = ErrorClassificationAgent()
    assert agent.classify_heuristic("duplicate key value violates unique constraint") == "LOAD"


def test_run_falls_back_to_llm_only_when_heuristic_is_unknown():
    agent = ErrorClassificationAgent()
    result = agent.run("completely ambiguous failure with no keywords")
    # AGENTS_ENABLED=false -> call_model returns "" -> category falls back to UNKNOWN
    assert result["error_category"] == "UNKNOWN"
    assert result["source"] == "llm"


def test_run_uses_heuristic_when_available():
    agent = ErrorClassificationAgent()
    result = agent.run("'wafer' is a required property")
    assert result["error_category"] == "SCHEMA"
    assert result["source"] == "heuristic"
