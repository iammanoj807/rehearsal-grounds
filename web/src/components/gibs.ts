// NASA GIBS WMTS tile templates (Web Mercator, EPSG:3857).
// Blue Marble shaded relief for the world view; the Landsat WELD true-colour
// annual composite (year 2000, about 38 m per pixel at level 12) close up.

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best'

export const BLUE_MARBLE = {
  url: `${GIBS}/BlueMarble_ShadedRelief_Bathymetry/default/2004-08-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
  maxNativeZoom: 8,
}

export const LANDSAT_WELD = {
  url: `${GIBS}/Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual/default/2000-12-01/GoogleMapsCompatible_Level12/{z}/{y}/{x}.jpeg`,
  maxNativeZoom: 12,
}

export const GIBS_ATTRIBUTION =
  'Imagery: <a href="https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api">NASA GIBS</a> (Blue Marble; Landsat WELD 2000)'

// Keep Leaflet inside valid Web Mercator tiles so it never requests out-of-range tiles.
export const WORLD_BOUNDS: [[number, number], [number, number]] = [
  [-84.9, -179.9],
  [84.9, 179.9],
]
