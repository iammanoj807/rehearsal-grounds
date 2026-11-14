"""Pydantic models: the one data contract shared by export, tests and the web app."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Target(Strict):
    id: str
    name: str
    body: Literal["moon", "mars"]
    description: str
    description_source_url: str
    source_url: str
    data_url: str
    citation: str
    resolution_m: float
    n_patches: int
    centre_lat: float
    centre_lon: float
    extent_km: float
    sigma: float
    n_sites: int
    hillshade_png: str
    data_note: Optional[str] = None


class Region(Strict):
    id: str
    name: str
    country: str
    set: Literal["well_studied", "discovery", "crater_benchmark"]
    lat: float
    lon: float
    source_url: str
    note: Optional[str] = None
    n_patches: int
    n_searchable: int
    worldcover_available: bool


class SubScores(Strict):
    relief: float = Field(ge=0, le=100)
    slope: float = Field(ge=0, le=100)
    roughness: float = Field(ge=0, le=100)
    shape: float = Field(ge=0, le=100)
    embedding: float = Field(ge=0, le=100)


class Terrain(Strict):
    relief_m: float
    slope_p50_deg: float
    slope_p90_deg: float
    rough_std_m: float
    bowl_index: float
    tri_m: float
    hypsometric_integral: float


class Environment(Strict):
    t2m_mean_c: Optional[float] = None
    t2m_min_c: Optional[float] = None
    t2m_max_c: Optional[float] = None
    t2m_range_c: Optional[float] = None
    precip_mm_per_day: Optional[float] = None
    rh_pct: Optional[float] = None
    solar_kwh_m2_day: Optional[float] = None
    bare_fraction: Optional[float] = None
    snow_ice_fraction: Optional[float] = None
    vegetation_fraction: Optional[float] = None
    water_fraction: Optional[float] = None
    worldcover_available: bool = True
    power_source: Optional[str] = None


class Novelty(Strict):
    status: Literal["well_studied", "less_studied"]
    basis: Optional[Literal["catalogue_distance", "well_studied_region"]] = None
    nearest_known_analog: str
    distance_km: float
    source_url: str


class Images(Strict):
    earth_hillshade: str
    target_hillshade: str


class Match(Strict):
    rank: int
    site_id: str
    region_id: str
    region_name: str
    region_set: str
    lat: float
    lon: float
    score: float = Field(ge=0, le=100)
    best_pair_score: float = Field(ge=0, le=100)
    s_morph: float
    s_embed: float
    sub_scores: SubScores
    terrain: Terrain
    target_terrain: Terrain
    target_patch_id: str
    environment: Optional[Environment] = None
    novelty: Optional[Novelty] = None
    strong_match: list[str]
    breaks_down: list[str]
    tests_suited: list[str]
    images: Images


class Results(Strict):
    target_id: str
    generated_at: str
    config_hash: str
    sigma: float
    n_candidates: int
    n_target_patches: int
    target_coverage: dict[str, float]
    matches: list[Match]


class Dataset(Strict):
    id: str
    name: str
    agency: str
    url: str
    used_for: str
    licence: str
    attribution: str
    citation: Optional[str] = None
    downloaded: Optional[str] = None


class Sources(Strict):
    generated_at: str
    datasets: list[Dataset]
