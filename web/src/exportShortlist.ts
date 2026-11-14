import type { Match, Target } from './types.ts'

const MONTH = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const ATTRIBUTION =
  'Rehearsal Grounds (NASA Space Apps 2026). Similarity scores for candidate analogs, not certifications. Data: NASA LRO LOLA (GSFC PGDA, Barker et al. 2021), USGS Mars 2020 CTX DTM (Fergason et al. 2020), ESA Copernicus DEM GLO-30, ESA WorldCover 2021, NASA POWER.'

export const monthNames = (months: number[] | null | undefined): string =>
  months && months.length ? months.map((m) => MONTH[m - 1]).join(', ') : ''

function rows(target: Target, matches: Match[]) {
  return matches.map((m) => ({
    rank: m.rank,
    region: m.region_name,
    site_id: m.site_id,
    lat: m.lat,
    lon: m.lon,
    similarity_score: Number(m.score.toFixed(2)),
    lighting_similarity: m.lighting ? Number(m.lighting.similarity.toFixed(1)) : '',
    best_months: monthNames(m.best_months),
    novelty: m.novelty ? (m.novelty.status === 'less_studied' ? 'Outside our analog catalogue' : 'Near a known analog') : '',
    nearest_known_analog: m.novelty?.nearest_known_analog ?? '',
    target: target.name,
  }))
}

function csvCell(v: unknown): string {
  const s = String(v ?? '')
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toCsv(target: Target, matches: Match[]): string {
  const r = rows(target, matches)
  const head = Object.keys(r[0] ?? { rank: '' })
  return [`# ${ATTRIBUTION}`, head.join(','), ...r.map((x) => head.map((k) => csvCell((x as Record<string, unknown>)[k])).join(','))].join('\n')
}

export function toGeoJson(target: Target, matches: Match[]): string {
  return JSON.stringify(
    {
      type: 'FeatureCollection',
      attribution: ATTRIBUTION,
      features: rows(target, matches).map((x) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [x.lon, x.lat] },
        properties: x,
      })),
    },
    null,
    1,
  )
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export function toKml(target: Target, matches: Match[]): string {
  const marks = rows(target, matches)
    .map(
      (x) => `  <Placemark>
    <name>${esc(`#${x.rank} ${x.region}`)}</name>
    <description>${esc(`Similarity ${x.similarity_score}${x.lighting_similarity !== '' ? ` · lighting ${x.lighting_similarity}` : ''}${x.best_months ? ` · best months ${x.best_months}` : ''} · ${x.novelty}`)}</description>
    <Point><coordinates>${x.lon},${x.lat},0</coordinates></Point>
  </Placemark>`,
    )
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>${esc(`Rehearsal Grounds: candidate analogs for ${target.name}`)}</name>
  <description>${esc(ATTRIBUTION)}</description>
${marks}
</Document>
</kml>
`
}

export function downloadText(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
