"""Tests for the GenAI boundary layer, running in offline (rule-based) mode."""
from pathlib import Path

import pytest

from pulseroute.graph import Graph
from pulseroute.llm_agent import LLMAgent, RuleBasedParser

DATA = Path(__file__).resolve().parents[1] / "data" / "stadium_graph.json"


@pytest.fixture(scope="module")
def graph():
    return Graph.from_json(DATA)


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
    text = agent.narrate(graph, result)
    assert "step-free" in text.lower()


def test_end_to_end_offline(agent, graph):
    """Full pipeline: NL -> request -> route -> narration, no network."""
    req = agent.parse_request("from gate C to first aid")
    result = graph.find_route(req)
    text = agent.narrate(graph, result)
    assert "First Aid" in text
