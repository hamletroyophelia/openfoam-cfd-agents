from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


Vector3 = tuple[float, float, float]


class CaseConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    selected_time: str = Field(pattern=r'^\d+(?:\.\d+)?$')
    expected_partitions: int = Field(ge=1)
    required_fields: list[str] = Field(min_length=1)
    format: Literal['decomposed'] = 'decomposed'


class BodyConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    kind: Literal['cylinder', 'sphere']
    center: Vector3
    diameter: float = Field(gt=0)
    span: float | None = Field(default=None, gt=0)


class PhysicsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    reference_length: float = Field(gt=0)
    reference_velocity: float = Field(gt=0)
    reference_length_symbol: str = Field(default='L_ref', pattern=r'^[A-Za-z][A-Za-z0-9_]*$')
    reference_velocity_symbol: str = Field(default='U_ref', pattern=r'^[A-Za-z][A-Za-z0-9_]*$')
    streamwise: Vector3
    cross_stream: Vector3
    spanwise: Vector3
    gravity: Vector3 | None
    body: BodyConfig

    @model_validator(mode='after')
    def axes_are_orthonormal(self):
        axes = (self.streamwise, self.cross_stream, self.spanwise)
        norms = [math.sqrt(sum(value * value for value in axis)) for axis in axes]
        dots = [sum(a * b for a, b in zip(axes[i], axes[j]))
                for i, j in ((0, 1), (0, 2), (1, 2))]
        handed = sum(self.streamwise[i] * (
            self.cross_stream[(i + 1) % 3] * self.spanwise[(i + 2) % 3]
            - self.cross_stream[(i + 2) % 3] * self.spanwise[(i + 1) % 3]) for i in range(3))
        if any(not math.isclose(value, 1, abs_tol=1e-8) for value in norms) or \
                any(not math.isclose(value, 0, abs_tol=1e-8) for value in dots) or handed < 1 - 1e-8:
            raise ValueError('streamwise, cross_stream and spanwise must be right-handed orthonormal axes')
        return self


class RenderConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    slice_origin: Vector3
    slice_normal: Vector3
    roi: tuple[float, float, float, float, float, float]
    resolution: tuple[int, int]
    preview_resolution: tuple[int, int]
    data_resolution: tuple[int, int] = (640, 360)
    velocity_star_range: tuple[float, float]
    vorticity_star_range: tuple[float, float]
    qstar_threshold: float = Field(gt=0)
    velocity_colormap: str = 'Viridis (matplotlib)'
    vorticity_colormap: str = 'Cool to Warm'
    font_family: str = 'Arial'
    font_size: int = Field(default=24, ge=12)
    q_camera_position: Vector3 = (16, -18, 13)
    q_camera_focal_point: Vector3 = (5, 0, 0)
    q_camera_view_up: Vector3 = (0, 0, 1)
    q_camera_parallel_scale: float = Field(default=7, gt=0)

    @model_validator(mode='after')
    def valid_ranges(self):
        ranges = (self.velocity_star_range, self.vorticity_star_range,
                  (self.roi[0], self.roi[1]), (self.roi[2], self.roi[3]), (self.roi[4], self.roi[5]))
        if any(low >= high for low, high in ranges):
            raise ValueError('render ranges must increase')
        if min(*self.resolution, *self.preview_resolution, *self.data_resolution) < 180:
            raise ValueError('render dimensions must be at least 320 pixels')
        normal = math.sqrt(sum(value * value for value in self.slice_normal))
        if not math.isclose(normal, 1, abs_tol=1e-8):
            raise ValueError('slice_normal must be a unit vector')
        return self


class StatisticsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    window: tuple[float, float]
    confidence_level: float = Field(gt=0, lt=1)

    @model_validator(mode='after')
    def increasing(self):
        if self.window[0] >= self.window[1]:
            raise ValueError('statistics window must increase')
        return self


class AnimationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    enabled: bool = False
    window_star: tuple[float, float] | None = None
    target_delta_time_star: float | None = Field(default=None, gt=0)
    reference_strouhal: float | None = Field(default=None, gt=0)
    minimum_frames_per_period: int = Field(default=20, ge=12)
    output_fps: int = Field(default=24, ge=1, le=120)
    interpolation: Literal['forbidden'] = 'forbidden'

    @model_validator(mode='after')
    def validate_animation_contract(self):
        if not self.enabled:
            return self
        if self.window_star is None or self.window_star[0] >= self.window_star[1]:
            raise ValueError('enabled animation requires an increasing window_star')
        if self.target_delta_time_star is None and self.reference_strouhal is None:
            raise ValueError('enabled animation requires target_delta_time_star or reference_strouhal')
        return self


class ResourceConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    processes: int = Field(ge=1)
    threads: int = Field(ge=1)
    memory_gib: float = Field(gt=0)


class VisualizationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal[2] = 2
    case: CaseConfig
    physics: PhysicsConfig
    render: RenderConfig
    statistics: StatisticsConfig
    animation: AnimationConfig = AnimationConfig()
    resources: ResourceConfig


def load_visualization_config(path: Path) -> VisualizationConfig:
    payload = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('viz.yaml must contain one mapping')
    return VisualizationConfig.model_validate(payload)
