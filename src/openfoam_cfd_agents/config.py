"""Validated YAML configuration for the cross-stage CFD workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SolverConfig(StrictModel):
    platform: Literal["openfoam"] = "openfoam"
    version: Literal["foundation-14"] = "foundation-14"
    application: Literal["foamRun"] = "foamRun"


class PhysicsConfig(StrictModel):
    flow_type: str = "incompressible"
    transient: bool = True
    turbulence_model: str = "auto"
    multiphase_model: str = "none"


class VerificationConfig(StrictModel):
    mesh_levels: list[str] = Field(default_factory=lambda: ["coarse", "medium", "fine"], min_length=3)
    timestep_levels: list[str] = Field(
        default_factory=lambda: ["large", "medium", "small"], min_length=3
    )
    domain_independence: bool = False
    gci_analysis: bool = True
    gci_limit: float = Field(default=0.02, gt=0)


class HpcConfig(StrictModel):
    process_counts: list[PositiveInt] = Field(
        default_factory=lambda: [1, 2, 4, 8, 16], min_length=1
    )
    benchmark_steps: int = Field(default=500, ge=1)
    test_smt: bool = True
    test_decomposition_methods: bool = True


class MonitoringConfig(StrictModel):
    residuals: bool = True
    courant_number: bool = True
    conservation_errors: bool = True
    force_coefficients: bool = True
    automatic_stop: bool = True
    max_courant: float = Field(default=1.0, gt=0)
    max_abs_cumulative_continuity_error: float = Field(default=1e-6, gt=0)
    max_final_residual: float = Field(default=1e-3, gt=0)
    min_time_steps: int = Field(default=1, ge=1)


class PostprocessingConfig(StrictModel):
    formats: list[str] = Field(default_factory=lambda: ["csv", "png", "vtk"])
    fields: list[str] = Field(default_factory=lambda: ["velocity", "pressure", "vorticity"])
    vortex_methods: list[str] = Field(default_factory=lambda: ["Q", "lambda2"])


class ReportConfig(StrictModel):
    formats: list[Literal["markdown", "html", "pdf"]] = Field(
        default_factory=lambda: ["markdown"]
    )


class WorkflowConfig(StrictModel):
    solver: SolverConfig = Field(default_factory=SolverConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    hpc: HpcConfig = Field(default_factory=HpcConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    postprocessing: PostprocessingConfig = Field(default_factory=PostprocessingConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)


def load_config(path: Path) -> WorkflowConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow configuration must be a YAML mapping")
    return WorkflowConfig.model_validate(data)
