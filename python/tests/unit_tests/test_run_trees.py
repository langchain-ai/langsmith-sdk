from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from langsmith import run_trees
from langsmith.client import Client


def test_run_tree_accepts_tpe() -> None:
    mock_client = MagicMock(spec=Client)
    run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        client=mock_client,
        executor=ThreadPoolExecutor(),
    )


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (
            "20240412T202937370454Z152ce25c-064e-4742-bf36-8bb0389f8805.20240412T202937627763Zfe8b541f-e75a-4ee6-b92d-732710897194.20240412T202937708023Z625b30ed-2fbb-4387-81b1-cb5d6221e5b4.20240412T202937775748Z448dc09f-ad54-4475-b3a4-fa43018ca621.20240412T202937981350Z4cd59ea4-491e-4ed9-923f-48cd93e03755.20240412T202938078862Zcd168cf7-ee72-48c2-8ec0-50ab09821973.20240412T202938152278Z32481c1a-b83c-4b53-a52e-1ea893ffba51",
            [
                (
                    datetime(2024, 4, 12, 20, 29, 37, 370454),
                    UUID("152ce25c-064e-4742-bf36-8bb0389f8805"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 627763),
                    UUID("fe8b541f-e75a-4ee6-b92d-732710897194"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 708023),
                    UUID("625b30ed-2fbb-4387-81b1-cb5d6221e5b4"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 775748),
                    UUID("448dc09f-ad54-4475-b3a4-fa43018ca621"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 981350),
                    UUID("4cd59ea4-491e-4ed9-923f-48cd93e03755"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 38, 78862),
                    UUID("cd168cf7-ee72-48c2-8ec0-50ab09821973"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 38, 152278),
                    UUID("32481c1a-b83c-4b53-a52e-1ea893ffba51"),
                ),
            ],
        ),
    ],
)
def test_parse_dotted_order(inputs, expected):
    assert run_trees._parse_dotted_order(inputs) == expected


def test_run_tree_events_not_null():
    mock_client = MagicMock(spec=Client)
    run_tree = run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        client=mock_client,
        executor=ThreadPoolExecutor(),
        events=None,
    )
    assert run_tree.events == []
