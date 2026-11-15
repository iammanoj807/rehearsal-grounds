"""Pydantic models: the one data contract shared by export, tests and the web app."""

from __future__ import annotations

from typing import Any, Literal, Optional

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
    artemis_iii_region: Optional[str] = None
    sun_band: Optional["SunBand"] = None


class SunBand(Strict):
    """Noon Sun elevations over a year at the target's latitude (Moon targets only)."""
    latitude_deg: float
    low_deg: float
    high_deg: float
    elevations_used: list[float]
    preview_elevation_deg: float
    jett5_region_id: Optional[str] = None
    jett5_low_sun_min: Optional[list[float]] = None


class ArtemisCoverage(Strict):
    """Which of NASA's named Artemis III candidate regions have a target here."""
    source_url: str
    release_date: str
    regions: list[str]
    covered: list[str]
    n_regions: int
    n_covered: int


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
    before_you_go: Optional[list["SourcedNote"]] = None


class SourcedNote(Strict):
    text: str
    source_url: str


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
    dense_veg_fraction: Optional[float] = None
    sparse_veg_fraction: Optional[float] = None
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
    lowsun_earth: Optional[str] = None
    lowsun_target: Optional[str] = None


class ShadowPoint(Strict):
    elevation_deg: float
    target: float = Field(ge=0, le=1)
    earth: float = Field(ge=0, le=1)


class Lighting(Strict):
    """Low-sun shadow comparison; a separate panel, never part of the similarity score."""
    similarity: float = Field(ge=0, le=100)
    elevations: list[float]
    shadow: list[ShadowPoint]
    edge_limited_target: bool
    edge_limited_earth: bool
    footprint_matched: bool = False


class MonthCal(Strict):
    month: int = Field(ge=1, le=12)
    daylight_h: float = Field(ge=0, le=24)
    low_sun_h: Optional[float] = Field(default=None, ge=0, le=24)
    t2m_min_avg_c: Optional[float] = None  # mean daily low (NASA POWER T2M_MIN_AVG)
    t2m_max_avg_c: Optional[float] = None  # mean daily high (NASA POWER T2M_MAX_AVG)
    precip_mm_per_day: Optional[float] = None


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
    lighting: Optional[Lighting] = None
    calendar: Optional[list[MonthCal]] = None
    best_months: Optional[list[int]] = None
    best_months_rule: Optional[str] = None


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


class UsualRegion(Strict):
    """Best patch of one well-studied region for one target, masks on and off."""
    region_id: str
    name: str
    best_score: Optional[float] = Field(default=None, ge=0, le=100)
    rank: Optional[int] = None
    best_patch_id: Optional[str] = None
    n_candidates: int
    best_score_masks_off: float = Field(ge=0, le=100)
    rank_masks_off: int
    n_candidates_masks_off: int
    best_patch_masked: bool
    field_test: Optional[str] = None


class Outranking(Strict):
    rank: int
    site_id: str
    region_id: str
    score: float = Field(ge=0, le=100)
    sub_scores: SubScores
    closer_groups: list[str]


class FieldTestCompare(Strict):
    region_id: str
    best_patch_id: str
    score: float = Field(ge=0, le=100)
    rank: int
    sub_scores: SubScores
    outranked_by: list[Outranking]


class UsualTarget(Strict):
    sigma: float
    regions: list[UsualRegion]
    field_test: Optional[FieldTestCompare] = None


class FieldTestInfo(Strict):
    name: str
    when: str
    where: str
    summary: str
    source_urls: list[str]


class UsualSites(Strict):
    field_test: Optional[FieldTestInfo] = None
    field_test_region_id: Optional[str] = None
    targets: dict[str, UsualTarget]


class LightingCheck(Strict):
    check: str
    passed: bool
    detail: str


class LightingInfo(Strict):
    """Lighting self-checks, settings, rules and limits for the Validation and About pages."""
    checks: list[LightingCheck]
    settings: dict[str, Any]
    rules: dict[str, Any]
    limits: list[str]
    refraction_note: str
    refraction_source_url: str


Target.model_rebuild()
Region.model_rebuild()

