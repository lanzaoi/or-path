"""Unit tests for spark-x2.6 / LLM 429 rate-limit automatic retry in studio_analyzer."""
from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

import pytest

from orpath.studio_analyzer import call_llm_reasoner


class _FakeSSEStream:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [ln.encode("utf-8") for ln in lines]

    def __enter__(self) -> _FakeSSEStream:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


def _make_429_error(msg: str = '{"error":{"code":"11202","message":"Rate limit exceeded (429)"}}', retry_after: str | None = None) -> urllib.error.HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    fp = io.BytesIO(msg.encode("utf-8"))
    return urllib.error.HTTPError(
        url="https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs=hdrs,
        fp=fp,
    )


def test_spark_x26_429_rate_limit_retries_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """When spark-x2.6 returns HTTP 429 on initial calls, call_llm_reasoner retries and succeeds."""
    monkeypatch.setenv("ORPATH_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("ORPATH_LLM_RETRY_DELAY", "0.01")

    valid_payload = {
        "domain_diagnosis": {
            "problem_class": "tsp",
            "domain_name": "TSP",
            "recommended_algorithm": "ortools",
            "algorithm_comparison": [],
            "rationale": "ok",
        },
        "data_alignment": {"matched_variables": [], "missing_or_warnings": []},
        "clarification_questions": [],
    }
    sse_lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"thinking..."}}]}\n',
        f'data: {json.dumps({"choices": [{"delta": {"content": json.dumps(valid_payload)}}]})}\n',
        "data: [DONE]\n",
    ]

    calls = {"count": 0}

    def fake_urlopen(req, timeout=75.0):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise _make_429_error(retry_after="0.01")
        return _FakeSSEStream(sse_lines)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = call_llm_reasoner(
            api_key="ak-test-spark-key",
            prompt="test tsp",
            statement_text="8 nodes tsp",
            data_profile={"slug": "test-tsp", "total_files": 1},
            model="spark-x2.6",
        )

    assert res is not None
    assert not res.get("failed")
    assert res.get("model_used") == "spark-x2.6"
    assert res.get("retry_count") == 2
    assert calls["count"] == 3
    assert res["domain_diagnosis"]["problem_class"] == "tsp"


def test_spark_x26_429_exhausts_retries_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """When HTTP 429 persists past max_retries, call_llm_reasoner returns a structured error dict."""
    monkeypatch.setenv("ORPATH_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("ORPATH_LLM_RETRY_DELAY", "0.01")

    calls = {"count": 0}

    def fake_urlopen(req, timeout=75.0):
        calls["count"] += 1
        raise _make_429_error()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = call_llm_reasoner(
            api_key="ak-test-spark-key",
            prompt="test",
            statement_text="test",
            data_profile={"slug": "test"},
            model="spark-x2.6",
        )

    assert res is not None
    assert res.get("failed") is True
    assert "HTTP 429" in str(res.get("error"))
    assert calls["count"] == 3


def test_spark_x26_mid_stream_rate_limit_error_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """When an SSE rate-limit error frame arrives mid-stream after partial reasoning/content tokens, retry and succeed."""
    monkeypatch.setenv("ORPATH_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("ORPATH_LLM_RETRY_DELAY", "0.01")

    valid_payload = {
        "domain_diagnosis": {
            "problem_class": "vrp",
            "domain_name": "CVRP",
            "recommended_algorithm": "ortools",
            "algorithm_comparison": [],
            "rationale": "ok",
        },
        "data_alignment": {"matched_variables": [], "missing_or_warnings": []},
        "clarification_questions": [],
    }
    mid_stream_err_lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"partial thinking..."}}]}\n',
        'data: {"choices":[{"delta":{"content":"{\\"domain_diagnosis\\":"}}]}\n',
        'data: {"error":{"code":"11202","message":"QPS rate limit exceeded (429)"}}\n',
    ]
    good_sse_lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"complete thinking"}}]}\n',
        f'data: {json.dumps({"choices": [{"delta": {"content": json.dumps(valid_payload)}}]})}\n',
        "data: [DONE]\n",
    ]

    calls = {"count": 0}

    def fake_urlopen(req, timeout=75.0):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeSSEStream(mid_stream_err_lines)
        return _FakeSSEStream(good_sse_lines)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = call_llm_reasoner(
            api_key="ak-test-spark-key",
            prompt="test vrp",
            statement_text="cvrp",
            data_profile={"slug": "test-vrp"},
            model="spark-x2.6",
        )

    assert res is not None
    assert not res.get("failed")
    assert res.get("retry_count") == 1
    assert calls["count"] == 2
    assert res["domain_diagnosis"]["problem_class"] == "vrp"
    assert res["reasoning_content"] == "complete thinking"

