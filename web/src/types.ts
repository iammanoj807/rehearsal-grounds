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
  snow_ice_fraction?: number | null
  vegetation_fraction?: number | null
  water_fraction?: number | null
  worldcover_available: boolean
  power_source?: string | null
}

export interface Novelty {
  status: 'well_studied' | 'less_studied'
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
  images: { earth_hillshade: string; target_hillshade: string }
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
