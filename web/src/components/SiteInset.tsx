import { AttributionControl, MapContainer, Rectangle, TileLayer } from 'react-leaflet'
import { BLUE_MARBLE, GIBS_ATTRIBUTION, LANDSAT_WELD, WORLD_BOUNDS, hideEmptyTile } from './gibs.ts'

/** Close-up of one site on Landsat imagery with the matched 3.84 km patch outlined. */
export default function SiteInset({ lat, lon, sizeKm }: { lat: number; lon: number; sizeKm: number }) {
  const dLat = sizeKm / 2 / 111.32
  const dLon = sizeKm / 2 / (111.32 * Math.max(Math.cos((lat * Math.PI) / 180), 0.05))
  const box: [[number, number], [number, number]] = [
    [lat - dLat, lon - dLon],
    [lat + dLat, lon + dLon],
  ]
  return (
    <MapContainer
      className="site-inset"
      center={[lat, lon]}
      zoom={11}
      minZoom={3}
      maxZoom={13}
      maxBounds={WORLD_BOUNDS}
      scrollWheelZoom={false}
      aria-label="Satellite view of the candidate site"
      attributionControl={false}
    >
      <AttributionControl prefix='<a href="https://leafletjs.com">Leaflet</a>' />
      <TileLayer url={BLUE_MARBLE.url} maxNativeZoom={BLUE_MARBLE.maxNativeZoom} maxZoom={13} noWrap attribution={GIBS_ATTRIBUTION} />
      <TileLayer
        url={LANDSAT_WELD.url}
        maxNativeZoom={LANDSAT_WELD.maxNativeZoom}
        minZoom={9}
        maxZoom={13}
        noWrap
        crossOrigin="anonymous"
        eventHandlers={{ tileload: hideEmptyTile }}
      />
      <Rectangle bounds={box} pathOptions={{ color: '#7A3D1A', weight: 2, fill: false }} />
    </MapContainer>
  )
}
