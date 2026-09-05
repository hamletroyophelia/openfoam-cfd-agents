"""Mesh-convergence verification using Richardson extrapolation and GCI."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, StageStatus, evaluate_stage


class MeshStudyPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    label: str = Field(min_length=1)
    cells: int = Field(gt=0)
    value: float


class GCIResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    ordered_labels: list[str]
    observed_order: float
    extrapolated_value: float
    fine_gci: float
    medium_gci: float
    refinement_ratio_21: float
    refinement_ratio_32: float
    asymptotic_ratio: float


def _observed_order(
    *,
    epsilon_32: float,
    epsilon_21: float,
    ratio_21: float,
    ratio_32: float,
) -> float:
    if epsilon_21 == 0 or epsilon_32 == 0:
        raise ValueError("successive solution differences must be non-zero")
    if epsilon_21 * epsilon_32 <= 0:
        raise ValueError("non-monotonic convergence: GCI applicability is not established")

    sign = 1.0 if epsilon_32 / epsilon_21 > 0 else -1.0
    current = math.log(epsilon_32 / epsilon_21) / math.log(ratio_21)
    if current <= 0:
        raise ValueError("divergent sequence: differences must decrease toward the fine mesh")
    current = max(current, 1e-8)
    for _ in range(100):
        numerator = ratio_21**current - sign
        denominator = ratio_32**current - sign
        if numerator <= 0 or denominator <= 0:
            raise ValueError("mesh sequence does not permit a real observed order")
        correction = math.log(numerator / denominator)
        updated = (
            (math.log(abs(epsilon_32 / epsilon_21)) + correction)
            / math.log(ratio_21)
        )
        if updated <= 0 or not math.isfinite(updated):
            raise ValueError("positive finite observed order is not established")
        if abs(updated - current) < 1e-10:
            return updated
        current = max(updated, 1e-8)
    raise ValueError("observed-order iteration did not converge")


def calculate_gci(
    points: list[MeshStudyPoint],
    *,
    dimension: int = 3,
    safety_factor: float = 1.25,
) -> GCIResult:
    """Calculate the three-grid GCI with finest mesh indexed as level 1."""

    if len(points) != 3:
        raise ValueError("GCI requires exactly three mesh levels")
    if dimension < 1:
        raise ValueError("dimension must be at least one")
    if not math.isfinite(safety_factor) or safety_factor <= 1:
        raise ValueError("safety_factor must be greater than one")
    if len({point.cells for point in points}) != 3:
        raise ValueError("mesh levels must have distinct cell counts")

    ordered = sorted(points, key=lambda point: point.cells, reverse=True)
    fine, medium, coarse = ordered
    h1 = fine.cells ** (-1.0 / dimension)
    h2 = medium.cells ** (-1.0 / dimension)
    h3 = coarse.cells ** (-1.0 / dimension)
    ratio_21 = h2 / h1
    ratio_32 = h3 / h2
    if ratio_21 <= 1 or ratio_32 <= 1:
        raise ValueError("mesh levels must become successively coarser")

    epsilon_21 = medium.value - fine.value
    epsilon_32 = coarse.value - medium.value
    order = _observed_order(
        epsilon_32=epsilon_32,
        epsilon_21=epsilon_21,
        ratio_21=ratio_21,
        ratio_32=ratio_32,
    )
    denominator_21 = ratio_21**order - 1.0
    denominator_32 = ratio_32**order - 1.0
    extrapolated = (ratio_21**order * fine.value - medium.value) / denominator_21
    if fine.value == 0 or medium.value == 0 or extrapolated == 0:
        raise ValueError("GCI relative errors require non-zero solution values")

    fine_gci = safety_factor * abs((fine.value - medium.value) / fine.value) / denominator_21
    medium_gci = (
        safety_factor * abs((medium.value - coarse.value) / medium.value) / denominator_32
    )
    asymptotic_ratio = medium_gci / (ratio_21**order * fine_gci)
    return GCIResult(
        ordered_labels=[point.label for point in ordered],
        observed_order=order,
        extrapolated_value=extrapolated,
        fine_gci=fine_gci,
        medium_gci=medium_gci,
        refinement_ratio_21=ratio_21,
        refinement_ratio_32=ratio_32,
        asymptotic_ratio=asymptotic_ratio,
    )


class VerificationAgent:
    """Prepare GCI evidence and apply explicit verification gates."""

    def __init__(self, *, gci_limit: float = 0.02, minimum_order: float = 0.1) -> None:
        if not math.isfinite(gci_limit) or gci_limit <= 0:
            raise ValueError("gci_limit must be positive")
        if not math.isfinite(minimum_order) or minimum_order <= 0:
            raise ValueError("minimum_order must be positive and finite")
        self.gci_limit = gci_limit
        self.minimum_order = minimum_order

    def evaluate_mesh_study(
        self,
        points: list[MeshStudyPoint],
        *,
        dimension: int = 3,
        artifact: str | None = None,
    ) -> StageResult:
        try:
            gci = calculate_gci(points, dimension=dimension)
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            return StageResult(stage="mesh_verification", status=StageStatus.INCONCLUSIVE,
                               metrics={"applicable": False}, message=str(exc),
                               artifacts=[artifact] if artifact else [])
        metrics = gci.model_dump(mode="json")
        result = evaluate_stage(
            stage="mesh_verification",
            metrics=metrics,
            rules=[
                MetricRule(metric="fine_gci", operator="<=", threshold=self.gci_limit),
                MetricRule(
                    metric="observed_order",
                    operator=">=",
                    threshold=self.minimum_order,
                ),
            ],
            artifacts=[artifact] if artifact else [],
        )
        if result.status is StageStatus.PASSED:
            return result.model_copy(update={"metrics": {**metrics, "recommended_level": gci.ordered_labels[0]}})
        return result
