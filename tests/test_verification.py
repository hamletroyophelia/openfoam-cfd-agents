from __future__ import annotations

import importlib

import pytest


def _verification_module():
    try:
        return importlib.import_module("openfoam_cfd_agents.agents.verification")
    except ModuleNotFoundError as exc:
        raise AssertionError("mesh verification implementation is missing") from exc


def _study(module):
    return [
        module.MeshStudyPoint(label="coarse", cells=125_000, value=1.12),
        module.MeshStudyPoint(label="fine", cells=8_000_000, value=1.00),
        module.MeshStudyPoint(label="medium", cells=1_000_000, value=1.04),
    ]


def test_gci_is_computed_from_three_systematically_refined_meshes() -> None:
    verification = _verification_module()

    result = verification.calculate_gci(_study(verification), dimension=3)

    assert result.observed_order == pytest.approx(1.0)
    assert result.extrapolated_value == pytest.approx(0.96)
    assert result.fine_gci == pytest.approx(0.05)
    assert result.refinement_ratio_21 == pytest.approx(2.0)
    assert result.ordered_labels == ["fine", "medium", "coarse"]


def test_verification_agent_applies_a_machine_gci_threshold() -> None:
    verification = _verification_module()

    passed = verification.VerificationAgent(gci_limit=0.051).evaluate_mesh_study(
        _study(verification)
    )
    failed = verification.VerificationAgent(gci_limit=0.049).evaluate_mesh_study(
        _study(verification)
    )

    assert passed.status.value == "passed"
    assert passed.metrics["recommended_level"] == "fine"
    assert failed.status.value == "failed"


def test_duplicate_cell_counts_are_rejected_as_non_systematic_refinement() -> None:
    verification = _verification_module()
    points = [
        verification.MeshStudyPoint(label="a", cells=100, value=1.0),
        verification.MeshStudyPoint(label="b", cells=100, value=1.1),
        verification.MeshStudyPoint(label="c", cells=800, value=1.2),
    ]

    with pytest.raises(ValueError, match="distinct cell counts"):
        verification.calculate_gci(points)
