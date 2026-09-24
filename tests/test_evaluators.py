"""Verify graders detect corrupted evidence and the runner isolates support writes.

Use valid offline outputs as a starting point, then break individual contracts to
check that the correct score fails. Scripted model decisions exercise real graph,
review and storage behavior without calling a provider or uploading experiments.
"""

# --- Imports -----------------------------------------------------------------

import json
import os
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage
from test_agent import ScriptedModel, call

from agent.agent import build_agent
from agent.context import CustomerContext, RecommendationQuery
from agent.database import PROJECT_ROOT, get_recommendations
from evals import runner
from evals.evaluators import grade_case

# --- Pinned case references and valid output fixtures --------------------------

CASES = {
    case["inputs"]["case_id"]: case
    for case in json.loads((PROJECT_ROOT / "src/data/eval_cases.json").read_text())
}


def scores(case_id, output):
    """Apply the real grader with pinned references and expose feedback as a keyed assertion map."""
    case = CASES[case_id]
    return {
        r["key"]: r["score"] for r in grade_case(case["inputs"], output, case["outputs"])["results"]
    }


def recommendation_output():
    """Build valid offline tool/answer evidence to corrupt in grader mutation tests."""
    payload = get_recommendations(CustomerContext(1), RecommendationQuery(genre="Rock"))
    return {
        "completed": True,
        "rows": [],
        "proposals": [],
        "tools": [{"name": "recommend_music", "payload": payload}],
        "answer": "\n".join(
            f"{i['track']} by {i['artist']} [track:{i['track_id']}]" for i in payload["items"]
        ),
    }


# --- Mutation tests: plausible but incorrect outputs must fail -----------------


def test_correct_recommendation_passes_but_same_artist_fails_variety():
    """Separate a valid ordinary recommendation from failing the additional artist-variety
    contract.
    """
    output = recommendation_output()
    assert scores("recommend_rock", output)["case_pass"] == 1
    assert scores("recommend_variety", output)["artist_variety"] == 0


@pytest.mark.parametrize("case_id", CASES)
def test_missing_execution_cannot_pass(case_id):
    """Check every pinned scenario fails when the target produces no execution evidence."""
    assert scores(case_id, None)["case_pass"] == 0


@pytest.mark.parametrize(
    "mutation, metric",
    [
        ("missing_tool", "required_tool"),
        ("invented_id", "answer_contract"),
        ("invented_title", "catalog_grounding"),
        ("wrong_genre", "genre_match"),
        ("duplicate", "answer_contract"),
        ("unexpected_write", "write_scope"),
    ],
)
def test_recommendation_mutations(mutation, metric):
    """Corrupt one contract at a time and require both its metric and the overall case to fail."""
    output = recommendation_output()
    if mutation == "missing_tool":
        output["tools"] = []
    elif mutation == "invented_id":
        output["answer"] = output["answer"].replace("1146", "999999")
    elif mutation == "invented_title":
        output["tools"][0]["payload"]["items"][0]["track"] = "An invented song"
    elif mutation == "wrong_genre":
        output["tools"][0]["payload"]["items"][0]["genre"] = "Jazz"
    elif mutation == "duplicate":
        output["answer"] += " [track:1146]"
    else:
        output["rows"] = [{"invoice_id": 98}]
    assert scores("recommend_rock", output)[metric] == 0
    assert scores("recommend_rock", output)["case_pass"] == 0


def test_owned_track_and_nonmusic_are_rejected():
    """Inject a purchased video track and ensure ownership and music eligibility both catch it."""
    output = recommendation_output()
    output["tools"][0]["payload"]["items"][0]["track_id"] = 3247
    result = scores("recommend_rock", output)
    assert result["unowned"] == result["music_only"] == 0


def test_forged_purchase_is_rejected():
    """Detect both an unauthorized invoice line and disclosure of its title in the answer."""
    output = {
        "completed": True,
        "rows": [],
        "tools": [
            {
                "name": "get_my_purchases",
                "payload": {
                    "status": "ok",
                    "items": [{"invoice_line_id": 1, "invoice_id": 1, "track_id": 2}],
                },
            }
        ],
        "answer": "Balls to the Wall",
    }
    result = scores("purchase_foreign", output)
    assert result["purchase_scope"] == result["answer_contract"] == 0


# --- Real graph execution: reviewer decisions and temporary store lifecycle ----


@pytest.mark.parametrize("review", ["pending", "approve", "reject", "edit", "unauthorized"])
def test_runner_support_isolation(monkeypatch, review):
    """Exercise all reviewer paths, then corrupt stored evidence to verify gate and scope
    grading.
    """

    def factory(**kwargs):
        """Inject scripted decisions into the real agent while retaining the runner's
        checkpointer.
        """
        return build_agent(
            model=ScriptedModel(
                responses=[
                    call(
                        {"invoice_id": 98, "reason": "I do not recognize this invoice."},
                        tool_name="create_support_request",
                    ),
                    AIMessage(content="Done."),
                ]
            ),
            **kwargs,
        )

    monkeypatch.setattr(runner, "build_agent", factory)
    previous = os.environ["SUPPORT_DB_PATH"]
    case_id = "support_" + review
    output = runner.run_case(CASES[case_id]["inputs"])
    assert os.environ["SUPPORT_DB_PATH"] == previous
    assert not runner.Path(previous).exists()
    result = scores(case_id, output)
    assert result["approval_gate"] == result["support_state"] == 1
    if review in {"approve", "edit"}:
        assert result["expected_status"] == 1  # Includes edited-tool envelope parsing.
    corrupted = deepcopy(output)
    corrupted["rows_before_review"] = [{"invoice_id": 98}]
    assert scores(case_id, corrupted)["approval_gate"] == 0
    corrupted = deepcopy(output)
    corrupted["rows"] = [{"customer_id": 99, "invoice_id": 98, "status": "open", "reason": "bad"}]
    assert scores(case_id, corrupted)["support_state"] == 0


def test_runner_restores_store_on_provider_failure(monkeypatch):
    """Ensure an initialization exception restores the original support-store environment
    setting.
    """

    def broken(**kwargs):
        """Raise before graph construction to exercise cleanup without making a provider call."""
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(runner, "build_agent", broken)
    previous = os.environ["SUPPORT_DB_PATH"]
    with pytest.raises(RuntimeError):
        runner.run_case(CASES["purchase_owned"]["inputs"])
    assert os.environ["SUPPORT_DB_PATH"] == previous


# --- Grader calibration: typography must not create false failures -------------


def test_typographic_apostrophes_do_not_change_catalog_names():
    """Accept smart apostrophes but still fail a response that changes an actual track title."""
    output = recommendation_output()
    output["answer"] = output["answer"].replace("'", "’")
    assert scores("recommend_rock", output)["answer_contract"] == 1
    output["answer"] = output["answer"].replace("Nightrain", "An invented title")
    assert scores("recommend_rock", output)["answer_contract"] == 0
