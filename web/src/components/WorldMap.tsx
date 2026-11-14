import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { AttributionControl, MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { Match } from '../types.ts'
import { BLUE_MARBLE, GIBS_ATTRIBUTION, LANDSAT_WELD, WORLD_BOUNDS } from './gibs.ts'

interface Props {
  matches: Match[]
  selected: string | null
  onSelect: (siteId: string) => void
  fitKey: string
}

function markerIcon(m: Match, selected: boolean): L.DivIcon {
  const status = m.novelty?.status ?? 'pending'
  return L.divIcon({
    className: '',
    html: `<span class="pin pin-${status}${selected ? ' pin-selected' : ''}">${m.rank}</span>`,
    iconSize: selected ? [34, 34] : [26, 26],
    iconAnchor: selected ? [17, 17] : [13, 13],
  })
}

function FitToMatches({ matches, fitKey }: { matches: Match[]; fitKey: string }) {
  const map = useMap()
  useEffect(() => {
    if (!matches.length) return
    const bounds = L.latLngBounds(matches.map((m) => [m.lat, m.lon] as [number, number]))
    map.fitBounds(bounds, { padding: [36, 36], maxZoom: 6, animate: false })
    // Refit when the target, filter or loaded set changes, not on selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, matches.length, map])
  return null
}

function PanToSelected({ matches, selected }: { matches: Match[]; selected: string | null }) {
  const map = useMap()
  useEffect(() => {
    const m = matches.find((x) => x.site_id === selected)
    if (m && !map.getBounds().pad(-0.1).contains([m.lat, m.lon])) map.panTo([m.lat, m.lon])
  }, [selected, matches, map])
  return null
}

/** World map of ranked candidate sites; markers carry their rank number. */
export default function WorldMap({ matches, selected, onSelect, fitKey }: Props) {
  const ordered = useMemo(
    () => [...matches].sort((a, b) => (a.site_id === selected ? 1 : b.site_id === selected ? -1 : b.rank - a.rank)),
    [matches, selected],
  )
  return (
    <MapContainer
      className="world-map"
      center={[20, 0]}
      zoom={2}
      minZoom={0.5}
      maxZoom={12}
      zoomSnap={0.25}
      worldCopyJump={false}
      maxBounds={WORLD_BOUNDS}
      maxBoundsViscosity={1}
      scrollWheelZoom={false}
      aria-label="World map of candidate analog sites"
      attributionControl={false}
    >
      <AttributionControl prefix='<a href="https://leafletjs.com">Leaflet</a>' />
      <TileLayer url={BLUE_MARBLE.url} maxNativeZoom={BLUE_MARBLE.maxNativeZoom} maxZoom={8} noWrap bounds={WORLD_BOUNDS} attribution={GIBS_ATTRIBUTION} />
      <TileLayer url={LANDSAT_WELD.url} maxNativeZoom={LANDSAT_WELD.maxNativeZoom} minZoom={9} maxZoom={12} noWrap bounds={WORLD_BOUNDS} />
      <FitToMatches matches={matches} fitKey={fitKey} />
      <PanToSelected matches={matches} selected={selected} />
      {ordered.map((m) => (
        <Marker
          key={m.site_id}
          position={[m.lat, m.lon]}
          icon={markerIcon(m, m.site_id === selected)}
          zIndexOffset={m.site_id === selected ? 1000 : 0}
          keyboard={false}
          eventHandlers={{ click: () => onSelect(m.site_id) }}
        >
          <Tooltip direction="top" offset={[0, -12]}>
            #{m.rank} {m.region_name} · {m.score.toFixed(1)}
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  )
}
