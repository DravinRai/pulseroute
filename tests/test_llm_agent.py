"""Tests for the GenAI boundary layer, running in offline (rule-based) mode."""

import pytest

from pulseroute import VENUE_GRAPH_PATH
from pulseroute.graph import Graph
from pulseroute.llm_agent import (
    _VALID_NODE_IDS,
    ALIASES,
    LLMAgent,
    RuleBasedParser,
    _extract_json,
)


@pytest.fixture(scope="module")
def graph():
    return Graph.from_json(VENUE_GRAPH_PATH)


@pytest.fixture
def agent():
    # Force offline mode so tests never touch the network.
    return LLMAgent(use_llm=False)


def test_parser_detects_wheelchair(agent):
    req = agent.parse_request("from metro to section 114 in a wheelchair")
    assert req.origin == "metro"
    assert req.destination == "sec_114"
    assert req.step_free is True


def test_parser_detects_sustainability(agent):
    req = agent.parse_request("greenest way from metro to shuttle hub")
    assert req.optimize == "co2"


def test_parser_longest_alias_wins():
    """'accessible restroom' must beat the substring 'restroom'."""
    req = RuleBasedParser().parse("from south concourse to the accessible restroom")
    assert req.destination == "restroom_acc_S"


def test_parser_requires_two_locations(agent):
    with pytest.raises(ValueError):
        agent.parse_request("I am hungry")


def test_narration_flags_step_free(agent, graph):
    req = agent.parse_request("wheelchair route from metro to section 114")
    result = graph.find_route(req)
    text = agent.narrate(result)
    assert "step-free" in text.lower()


def test_end_to_end_offline(agent, graph):
    """Full pipeline: NL -> request -> route -> narration, no network."""
    req = agent.parse_request("from gate C to first aid")
    result = graph.find_route(req)
    text = agent.narrate(result)
    assert "First Aid" in text


# ---- guards on the LLM prompt path -------------------------------------
def test_valid_node_ids_are_precomputed_and_complete():
    """Regression: this list is built from ALIASES.values() and is interpolated
    into the Claude system prompt. It previously raised TypeError at request
    time because dict_values does not support set union — a crash that only
    surfaced once an API key was present."""
    assert isinstance(_VALID_NODE_IDS, tuple)
    assert set(_VALID_NODE_IDS) == set(ALIASES.values())
    assert "metro" in _VALID_NODE_IDS
    assert ", ".join(_VALID_NODE_IDS)  # must be interpolable into the prompt


def test_extract_json_pulls_object_from_prose():
    assert _extract_json('sure! {"a": 1} hope that helps') == '{"a": 1}'


def test_extract_json_rejects_missing_object():
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_agent_without_key_uses_offline_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert LLMAgent().use_llm is False
