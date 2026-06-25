import ast
from collections import Counter

from examples.use_cases.catalog import CATEGORIES, USE_CASES
from examples.use_cases.programs import program_for


def test_use_case_catalog_is_complete_and_unique() -> None:
    expected_counts = {
        "Robotics": 22,
        "Industrial automation": 18,
        "IoT and embedded devices": 13,
        "Smart buildings and homes": 12,
        "Agriculture and environmental monitoring": 13,
        "Logistics and warehouses": 12,
        "Vehicles and transportation": 10,
        "Healthcare and laboratories": 11,
        "Retail and hospitality": 10,
        "Edge IT and networking": 11,
        "Remote and disconnected operations": 10,
        "Privacy-sensitive applications": 8,
        "Multi-agent systems": 13,
        "Reasoning and decision-support workflows": 12,
        "Knowledge and retrieval": 10,
        "Human approval workflows": 10,
        "Protocol and middleware gateway": 9,
        "Development and research": 12,
        "Product patterns": 10,
        "Poor fits without additional systems": 10,
    }

    assert tuple(expected_counts) == CATEGORIES
    assert len(USE_CASES) == 236
    assert len({case.slug for case in USE_CASES}) == len(USE_CASES)
    assert Counter(case.category for case in USE_CASES) == expected_counts


def test_every_documented_program_is_valid_python() -> None:
    for case in USE_CASES:
        ast.parse(program_for(case), filename=case.slug)

