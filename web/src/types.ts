// Mirrors pipeline/schemas.py: the static data contract in public/data.

export type Body = 'moon' | 'mars'

export interface Target {
  id: string
  name: string
  body: Body
  description: string
  description_source_url: string
  source_url: string
  data_url: string
  citation: string
  resolution_m: number
  n_patches: number
  centre_lat: number
  centre_lon: number
  extent_km: number
  sigma: number
  n_sites: number
  hillshade_png: string
  data_note?: string | null
  artemis_iii_region?: string | null
  sun_band?: SunBand | null
}

export interface SunBand {
  latitude_deg: number
  low_deg: number
  high_deg: number
  elevations_used: number[]
  preview_elevation_deg: number
  jett5_region_id?: string | null
  jett5_low_sun_min?: number[] | null
}

export interface Region {
  id: string
  name: string
  country: string
  set: 'well_studied' | 'discovery' | 'crater_benchmark'
  lat: number
  lon: number
  source_url: string
  note?: string | null
  n_patches: number
  n_searchable: number
  worldcover_available: boolean
  before_you_go?: { text: string; source_url: string }[] | null
}

export interface SubScores {
  relief: number
  slope: number
  roughness: number
  shape: number
  embedding: number
}

export interface Terrain {
  relief_m: number
  slope_p50_deg: number
  slope_p90_deg: number
  rough_std_m: number
  bowl_index: number
  tri_m: number
  hypsometric_integral: number
}

export interface Environment {
  t2m_mean_c?: number | null
  t2m_min_c?: number | null
  t2m_max_c?: number | null
  t2m_range_c?: number | null
  precip_mm_per_day?: number | null
  rh_pct?: number | null
  solar_kwh_m2_day?: number | null
  bare_fraction?: number | null
  dense_veg_fraction?: number | null
  sparse_veg_fraction?: number | null
  snow_ice_fraction?: number | null
  vegetation_fraction?: number | null
  water_fraction?: number | null
  worldcover_available: boolean
  power_source?: string | null
}

export interface Novelty {
  status: 'well_studied' | 'less_studied'
  basis?: 'catalogue_distance' | 'well_studied_region' | null
  nearest_known_analog: string
  distance_km: number
  source_url: string
}

export interface Match {
  rank: number
  site_id: string
  region_id: string
  region_name: string
  region_set: string
  lat: number
  lon: number
  score: number
  best_pair_score: number
  s_morph: number
  s_embed: number
  sub_scores: SubScores
  terrain: Terrain
  target_terrain: Terrain
  target_patch_id: string
  environment?: Environment | null
  novelty?: Novelty | null
  strong_match: string[]
  breaks_down: string[]
  tests_suited: string[]
  images: { earth_hillshade: string; target_hillshade: string; lowsun_earth?: string | null; lowsun_target?: string | null }
  lighting?: Lighting | null
  calendar?: MonthCal[] | null
  best_months?: number[] | null
  best_months_rule?: string | null
}

export interface Lighting {
  similarity: number
  elevations: number[]
  shadow: { elevation_deg: number; target: number; earth: number }[]
  edge_limited_target: boolean
  edge_limited_earth: boolean
}

export interface MonthCal {
  month: number
  daylight_h: number
  low_sun_h?: number | null
  t2m_min_avg_c?: number | null
  t2m_max_avg_c?: number | null
  precip_mm_per_day?: number | null
}

export interface Results {
  target_id: string
  generated_at: string
  config_hash: string
  sigma: number
  n_candidates: number
  n_target_patches: number
  target_coverage: { share_close_90: number; share_close_99: number; median_best_percentile: number }
  matches: Match[]
}

export interface Dataset {
  id: string
  name: string
  agency: string
  url: string
  used_for: string
  licence: string
  attribution: string
  citation?: string | null
  downloaded?: string | null
}

export interface Sources {
  generated_at: string
  datasets: Dataset[]
}

export interface Meta {
  generated_at: string
  config_hash: string
  n_earth_patches: number
  n_searchable: number
  resolution_m: number
  patch_px: number
  weights: { morph: number; embed: number }
}

// validation.json is open-ended; pages read the parts they render.
export type Validation = Record<string, unknown>

export interface ArtemisCoverage {
  source_url: string
  release_date: string
  regions: string[]
  covered: string[]
  n_regions: number
  n_covered: number
}

export interface UsualRegion {
  region_id: string
  name: string
  best_score?: number | null
  rank?: number | null
  best_patch_id?: string | null
  n_candidates: number
  best_score_masks_off: number
  rank_masks_off: number
  n_candidates_masks_off: number
  best_patch_masked: boolean
  field_test?: string | null
}

export interface Outranking {
  rank: number
  site_id: string
  region_id: string
  score: number
  sub_scores: SubScores
  closer_groups: string[]
}

export interface UsualSites {
  field_test?: { name: string; when: string; where: string; summary: string; source_urls: string[] } | null
  field_test_region_id?: string | null
  targets: Record<
    string,
    {
      sigma: number
      regions: UsualRegion[]
      field_test?: {
        region_id: string
        best_patch_id: string
        score: number
        rank: number
        sub_scores: SubScores
        outranked_by: Outranking[]
      } | null
    }
  >
}

export interface LightingInfo {
  checks: { check: string; passed: boolean; detail: string }[]
  settings: Record<string, unknown>
  rules: Record<string, unknown>
  limits: string[]
  refraction_note: string
  refraction_source_url: string
}

