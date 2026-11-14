import { Link, useParams } from 'react-router-dom'
import LoadState from '../components/LoadState.tsx'
import ScoreBars from '../components/ScoreBars.tsx'
import SiteInset from '../components/SiteInset.tsx'
import { bodyLabel, dataUrl, fmt, latLon, pct, useJson } from '../data.ts'
import type { Match, Results, Target, Terrain } from '../types.ts'
import { NoveltyBadge } from './Explore.tsx'

const TERRAIN_ROWS: { key: keyof Terrain; label: string; unit: string; digits: number }[] = [
  { key: 'relief_m', label: 'Relief (5th–95th percentile height)', unit: ' m', digits: 0 },
  { key: 'slope_p50_deg', label: 'Median slope', unit: '°', digits: 1 },
  { key: 'slope_p90_deg', label: '90th-percentile slope', unit: '°', digits: 1 },
  { key: 'rough_std_m', label: 'Roughness (plane-fit spread)', unit: ' m', digits: 1 },
  { key: 'tri_m', label: 'Ruggedness index', unit: ' m', digits: 1 },
  { key: 'bowl_index', label: 'Bowl index (+ bowl, − dome)', unit: '', digits: 2 },
  { key: 'hypsometric_integral', label: 'Hypsometric integral', unit: '', digits: 2 },
]

function dossierMarkdown(t: Target, m: Match): string {
  const env = m.environment
  const lines = [
    `# Candidate analog #${m.rank} for ${t.name} (${bodyLabel(t.body)})`,
    '',
    `- Earth site: ${m.region_name}, ${latLon(m.lat, m.lon)}`,
    `- Similarity score (0-100): ${m.score.toFixed(1)}`,
    m.novelty
      ? `- Novelty: ${m.novelty.status.replace('_', ' ')}; nearest catalogued analog ${m.novelty.nearest_known_analog}, ${m.novelty.distance_km.toFixed(0)} km`
      : '- Novelty: not computed',
    '',
    '## Explanation bars (percentile vs random Earth patch pairs)',
    ...Object.entries(m.sub_scores).map(([k, v]) => `- ${k}: ${v.toFixed(0)}/100`),
    '',
    '## Terrain (3.84 km patch, 60 m grid)',
    `| Measure | ${bodyLabel(t.body)} target | Earth site |`,
    '| --- | --- | --- |',
    ...TERRAIN_ROWS.map((r) => `| ${r.label} | ${fmt(m.target_terrain[r.key], r.digits, r.unit)} | ${fmt(m.terrain[r.key], r.digits, r.unit)} |`),
    '',
    '## Environment (Earth site)',
    env
      ? [
          `- Mean / min / max temperature: ${fmt(env.t2m_mean_c, 1, ' °C')} / ${fmt(env.t2m_min_c, 1, ' °C')} / ${fmt(env.t2m_max_c, 1, ' °C')}`,
          `- Precipitation: ${fmt(env.precip_mm_per_day, 2, ' mm/day')}`,
          `- Bare ground / snow-ice (2 km): ${pct(env.bare_fraction)} / ${pct(env.snow_ice_fraction)}`,
        ].join('\n')
      : '- Not available',
    '',
    '## Strong match',
    ...m.strong_match.map((s) => `- ${s}`),
    '',
    '## Breaks down',
    ...m.breaks_down.map((s) => `- ${s}`),
    '',
    '## Tests suited (our scoring rules, not engineering limits)',
    ...(m.tests_suited.length ? m.tests_suited.map((s) => `- ${s}`) : ['- None of our rules fire for this site']),
    '',
    `Source: Rehearsal Grounds, ${window.location.href}`,
  ]
  return lines.join('\n')
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export default function SitePage() {
  const { targetId = '', siteId = '' } = useParams()
  const targets = useJson<Target[]>('targets.json')
  const results = useJson<Results>(`results/${targetId}.json`)
  const target = targets.data?.find((t) => t.id === targetId)
  const matches = results.data?.matches ?? []
  const idx = matches.findIndex((m) => m.site_id === decodeURIComponent(siteId))
  const m = idx >= 0 ? matches[idx] : null
  const prev = idx > 0 ? matches[idx - 1] : null
  const next = idx >= 0 && idx < matches.length - 1 ? matches[idx + 1] : null
  const back = `/?target=${targetId}`

  if (targets.error || results.error || targets.loading || results.loading) {
    return (
      <div className="page">
        <LoadState what="site" error={targets.error ?? results.error} loading={targets.loading || results.loading} retry={() => { targets.retry(); results.retry() }} />
      </div>
    )
  }
  if (!target || !m) {
    return (
      <div className="page narrow">
        <h1>Site not found</h1>
        <p>
          <Link to={back}>Back to the matches</Link>
        </p>
      </div>
    )
  }
  const body = bodyLabel(target.body)
  const env = m.environment

  return (
    <article className="page site">
      <p className="crumbs">
        <Link to={back}>← All matches for {target.name}</Link>
      </p>
      <header className="site-head">
        <div>
          <p className="eyebrow">Candidate analog #{m.rank} for {target.name}</p>
          <h1>{m.region_name}</h1>
          <p className="muted">
            {latLon(m.lat, m.lon)} · <NoveltyBadge m={m} />
            {m.novelty && (
              <>
                {' '}nearest catalogued analog: <a href={m.novelty.source_url}>{m.novelty.nearest_known_analog}</a>,{' '}
                {m.novelty.distance_km.toFixed(0)} km
              </>
            )}
          </p>
        </div>
        <div className="score-block" aria-label={`similarity score ${m.score.toFixed(1)} out of 100`}>
          <span className="score-number">{m.score.toFixed(1)}</span>
          <span className="score-label">similarity score (0–100)</span>
        </div>
      </header>

      <section className="split" aria-label="Side-by-side terrain">
        <figure className={`split-panel panel-${target.body}`}>
          <figcaption>
            <span className="panel-body">{body}</span> {target.name} · best-matching target patch
          </figcaption>
          <img
            src={dataUrl(m.images.target_hillshade)}
            alt={`Shaded relief of the ${target.name} target patch, 3.84 km across`}
            width={256}
            height={256}
          />
        </figure>
        <figure className="split-panel panel-earth">
          <figcaption>
            <span className="panel-body">Earth</span> {m.region_name} · matched patch
          </figcaption>
          <img
            src={dataUrl(m.images.earth_hillshade)}
            alt={`Shaded relief of the Earth patch in ${m.region_name}, 3.84 km across`}
            width={256}
            height={256}
          />
        </figure>
      </section>
      <p className="small muted center">
        Both views: 3.84 km across on a 60 m grid, light from the north-west at 45°, no vertical exaggeration, contrast
        stretched for display. Scale bars are 1 km.
      </p>

      <div className="site-grid">
        <section aria-labelledby="why">
          <h2 id="why">Why it matches</h2>
          <ScoreBars scores={m.sub_scores} />
          <p className="small muted">
            Bars: how close this pair is compared with random pairs of Earth patches from different regions (100 = closer
            than all). The score combines 60% terrain fingerprint ({(m.s_morph * 100).toFixed(0)}) and 40% image
            embedding ({(m.s_embed * 100).toFixed(0)}), averaged over the three best-matching target patches.
          </p>
          <h3>Strong match</h3>
          <ul className="reasons good">{m.strong_match.map((s) => <li key={s}>{s}</li>)}</ul>
          <h3>Breaks down</h3>
          <ul className="reasons bad">{m.breaks_down.map((s) => <li key={s}>{s}</li>)}</ul>
          <h3>What you could test here</h3>
          {m.tests_suited.length ? (
            <ul className="reasons">{m.tests_suited.map((s) => <li key={s}>{s}</li>)}</ul>
          ) : (
            <p>None of our test rules fire for this site.</p>
          )}
          <p className="small muted">Test suggestions come from simple rules on our own scores; they are not engineering limits.</p>
        </section>

        <section aria-labelledby="numbers">
          <h2 id="numbers">Terrain, side by side</h2>
          <table className="terrain-table">
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col">{body} target</th>
                <th scope="col">Earth site</th>
              </tr>
            </thead>
            <tbody>
              {TERRAIN_ROWS.map((r) => (
                <tr key={r.key}>
                  <th scope="row">{r.label}</th>
                  <td>{fmt(m.target_terrain[r.key], r.digits, r.unit)}</td>
                  <td>{fmt(m.terrain[r.key], r.digits, r.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>Environment at the Earth site</h2>
          {env ? (
            <table className="terrain-table">
              <tbody>
                <tr><th scope="row">Mean temperature</th><td>{fmt(env.t2m_mean_c, 1, ' °C')}</td></tr>
                <tr><th scope="row">Coldest / warmest monthly extreme</th><td>{fmt(env.t2m_min_c, 1, ' °C')} / {fmt(env.t2m_max_c, 1, ' °C')}</td></tr>
                <tr><th scope="row">Mean daily temperature range</th><td>{fmt(env.t2m_range_c, 1, ' °C')}</td></tr>
                <tr><th scope="row">Precipitation</th><td>{fmt(env.precip_mm_per_day, 2, ' mm/day')}</td></tr>
                <tr><th scope="row">Relative humidity</th><td>{fmt(env.rh_pct, 0, '%')}</td></tr>
                <tr><th scope="row">Sunlight at the surface</th><td>{fmt(env.solar_kwh_m2_day, 2, ' kWh/m²/day')}</td></tr>
                <tr><th scope="row">Bare ground within 2 km</th><td>{env.worldcover_available ? pct(env.bare_fraction) : 'no land-cover data'}</td></tr>
                <tr><th scope="row">Snow and ice within 2 km</th><td>{env.worldcover_available ? pct(env.snow_ice_fraction) : 'no land-cover data'}</td></tr>
                <tr><th scope="row">Vegetation, crops or buildings within 2 km</th><td>{env.worldcover_available ? pct(env.vegetation_fraction) : 'no land-cover data'}</td></tr>
              </tbody>
            </table>
          ) : (
            <p>Climate and land-cover values have not been computed for this site yet.</p>
          )}
          <p className="small muted">Climate: NASA POWER climatology (2001–2025 monthly means). Land cover: ESA WorldCover 2021.</p>

          <h2>Where it is</h2>
          <SiteInset lat={m.lat} lon={m.lon} sizeKm={3.84} />
          <p className="small muted">Landsat WELD true-colour annual composite (year 2000) from NASA GIBS. The box marks the matched 3.84 km patch.</p>
        </section>
      </div>

      <section className="limits" aria-labelledby="limits">
        <h2 id="limits">What Earth cannot reproduce</h2>
        <p>
          Terrain shape is only one part of an analog. No place on Earth reproduces {target.body === 'moon' ? 'the Moon’s gravity, vacuum' : 'Mars’ gravity, thin carbon-dioxide air'},
          radiation, regolith or mineralogy, and a 60 m grid cannot see boulders or small craters. Use these sites for
          the tests the terrain supports, and check everything else separately.
        </p>
      </section>

      <nav className="site-nav" aria-label="Other candidate sites">
        {prev ? <Link to={`/site/${targetId}/${encodeURIComponent(prev.site_id)}`}>← #{prev.rank} {prev.region_name}</Link> : <span />}
        <button type="button" onClick={() => download(`rehearsal-grounds_${targetId}_rank${m.rank}.md`, dossierMarkdown(target, m))}>
          Download dossier (Markdown)
        </button>
        {next ? <Link to={`/site/${targetId}/${encodeURIComponent(next.site_id)}`}>#{next.rank} {next.region_name} →</Link> : <span />}
      </nav>
    </article>
  )
}
