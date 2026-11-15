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

/**
 * Landsat WELD has no imagery in some places (Antarctica, Svalbard): GIBS then serves
 * an all-black tile. Hide such tiles so the Blue Marble layer underneath shows instead.
 * GIBS sends Access-Control-Allow-Origin: *, so the tile can be read with crossOrigin set.
 */
export function hideEmptyTile(e: { tile: HTMLElement }) {
  const img = e.tile as HTMLImageElement
  try {
    const c = document.createElement('canvas')
    c.width = 16
    c.height = 16
    const ctx = c.getContext('2d', { willReadFrequently: true })
    if (!ctx) return
    ctx.drawImage(img, 0, 0, 16, 16)
    const px = ctx.getImageData(0, 0, 16, 16).data
    let max = 0
    for (let i = 0; i < px.length; i += 4) max = Math.max(max, px[i], px[i + 1], px[i + 2])
    if (max < 8) img.style.visibility = 'hidden'
  } catch {
    // A tile that cannot be read stays visible.
  }
}

