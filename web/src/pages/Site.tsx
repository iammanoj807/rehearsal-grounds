import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import LoadState from '../components/LoadState.tsx'
import ScoreBars from '../components/ScoreBars.tsx'
import SiteInset from '../components/SiteInset.tsx'
import TerrainTwin from '../components/TerrainTwin.tsx'
import { bodyLabel, dataUrl, fmt, latLon, pct, useJson } from '../data.ts'
import { monthNames } from '../exportShortlist.ts'
import type { LightingInfo, Match, Region, Results, Target, Terrain } from '../types.ts'
import LightingPanel, { CalendarStrip } from '../components/LightingPanel.tsx'
import { NoveltyBadge, noveltyLabel, regionSetLabel } from './Explore.tsx'

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
      ? `- Novelty: ${noveltyLabel(m.novelty.status)}${m.novelty.basis === 'well_studied_region' ? ' (in a well-studied analog region)' : ''}; nearest catalogued analog ${m.novelty.nearest_known_analog}, ${m.novelty.distance_km.toFixed(0)} km`
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
    m.lighting ? `- Low-sun shadow similarity (separate panel): ${m.lighting.similarity.toFixed(0)}/100` : '- Low-sun shadow similarity: not applicable',
    m.best_months?.length ? `- Best months (our rules, not safety advice): ${monthNames(m.best_months)}. ${m.best_months_rule ?? ''}` : '',
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
  const [mode, setMode] = useState<'swipe' | 'side' | 'lowsun'>('swipe')
  const regions = useJson<Region[]>('regions.json')
  const linfo = useJson<LightingInfo>('lighting_info.json')

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
  const envTiles = env
    ? [
        { label: 'Mean temperature', value: fmt(env.t2m_mean_c, 1, ' °C') },
        { label: 'Coldest / warmest monthly extreme', value: `${fmt(env.t2m_min_c, 1, '°')} / ${fmt(env.t2m_max_c, 1, ' °C')}` },
        { label: 'Mean daily temperature range', value: fmt(env.t2m_range_c, 1, ' °C') },
        { label: 'Precipitation', value: fmt(env.precip_mm_per_day, 2, ' mm/day') },
        { label: 'Relative humidity', value: fmt(env.rh_pct, 0, '%') },
        { label: 'Sunlight at the surface', value: fmt(env.solar_kwh_m2_day, 2, ' kWh/m²/day') },
        { label: 'Bare ground within 2 km', value: env.worldcover_available ? pct(env.bare_fraction) : 'no land-cover data' },
        { label: 'Snow and ice within 2 km', value: env.worldcover_available ? pct(env.snow_ice_fraction) : 'no land-cover data' },
        ...(env.dense_veg_fraction != null && env.sparse_veg_fraction != null
          ? [
              { label: 'Trees, crops, buildings or wetland within 2 km', value: env.worldcover_available ? pct(env.dense_veg_fraction) : 'no land-cover data' },
              { label: 'Shrub, grass or moss within 2 km (WorldCover)', value: env.worldcover_available ? pct(env.sparse_veg_fraction) : 'no land-cover data' },
            ]
          : [{ label: 'Vegetation, crops or buildings within 2 km', value: env.worldcover_available ? pct(env.vegetation_fraction) : 'no land-cover data' }]),
      ]
    : []

  return (
    <article className={`site body-${target.body}`}>
      <header className="site-hero">
        <div className="page">
          <p className="crumbs">
            <Link to={back}>← All matches for {target.name}</Link>
          </p>
          <div className="site-head">
            <div>
              <p className="eyebrow">
                Candidate analog #{m.rank} · {target.name} ({body})
              </p>
              <h1>{m.region_name}</h1>
              <p className="mono coords">{latLon(m.lat, m.lon)}</p>
              <p className="site-tags">
                <NoveltyBadge m={m} />
                <span className="badge badge-plain">{regionSetLabel(m.region_set)}</span>
              </p>
              {m.novelty && (
                <p className="small muted">
                  {m.novelty.basis === 'well_studied_region' && 'In a well-studied analog region. '}
                  Nearest catalogued analog: <a href={m.novelty.source_url}>{m.novelty.nearest_known_analog}</a>,{' '}
                  {m.novelty.distance_km.toFixed(0)} km.
                </p>
              )}
            </div>
            <div className="score-block" aria-label={`similarity score ${m.score.toFixed(1)} out of 100`}>
              <span className="score-number">{m.score.toFixed(1)}</span>
              <span className="meter meter-score" aria-hidden="true">
                <span style={{ width: `${m.score}%` }} />
              </span>
              <span className="score-label">similarity score (0–100)</span>
            </div>
          </div>
        </div>
      </header>

      <div className="page">
        <section className="compare card" aria-label="Terrain comparison">
          <div className="compare-head">
            <h2>{body} patch vs Earth patch</h2>
            <div className="chips" role="group" aria-label="Comparison view">
              <button type="button" className="chip" aria-pressed={mode === 'swipe'} onClick={() => setMode('swipe')}>
                Swipe
              </button>
              <button type="button" className="chip" aria-pressed={mode === 'side'} onClick={() => setMode('side')}>
                Side by side
              </button>
              {m.images.lowsun_earth && m.images.lowsun_target && (
                <button type="button" className="chip" aria-pressed={mode === 'lowsun'} onClick={() => setMode('lowsun')}>
                  Low sun
                </button>
              )}
            </div>
          </div>
          {mode === 'lowsun' && m.images.lowsun_earth && m.images.lowsun_target && target.sun_band ? (
            <>
              <TerrainTwin
                size="lg"
                targetSrc={dataUrl(m.images.lowsun_target)}
                earthSrc={dataUrl(m.images.lowsun_earth)}
                targetAlt={`${target.name} target patch lit by a ${target.sun_band.preview_elevation_deg.toFixed(1)} degree Sun with cast shadows`}
                earthAlt={`Earth patch in ${m.region_name} lit by the same low Sun with cast shadows`}
                body={target.body}
                targetName={target.name}
                earthName={m.region_name}
              />
              <p className="small muted center">
                Low sun: light from the north-west at {target.sun_band.preview_elevation_deg.toFixed(1)}°, the middle of
                {' '}{target.name}’s noon Sun band ({target.sun_band.low_deg.toFixed(1)}–{target.sun_band.high_deg.toFixed(1)}°).
                Cast shadows are black; both views share one contrast stretch. The previews use each patch’s own
                surroundings; the lighting score gives the Earth patch the target’s visible surroundings, so a preview
                can show a few more distant shadows than the score counts.
                {target.sun_band.preview_elevation_deg < 1.5 &&
                  ' At a Sun this low, most of both patches is in shadow: that is the honest result, not a rendering fault.'}
              </p>
            </>
          ) : mode === 'swipe' ? (
            <TerrainTwin
              size="lg"
              targetSrc={dataUrl(m.images.target_hillshade)}
              earthSrc={dataUrl(m.images.earth_hillshade)}
              targetAlt={`Shaded relief of the ${target.name} target patch, 3.84 km across`}
              earthAlt={`Shaded relief of the Earth patch in ${m.region_name}, 3.84 km across`}
              body={target.body}
              targetName={target.name}
              earthName={m.region_name}
            />
          ) : (
            <div className="split">
              <figure className={`split-panel panel-${target.body}`}>
                <figcaption>
                  <i className={`dot dot-${target.body}`} aria-hidden="true" />
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
                  <i className="dot dot-earth" aria-hidden="true" />
                  <span className="panel-body">Earth</span> {m.region_name} · matched patch
                </figcaption>
                <img
                  src={dataUrl(m.images.earth_hillshade)}
                  alt={`Shaded relief of the Earth patch in ${m.region_name}, 3.84 km across`}
                  width={256}
                  height={256}
                />
              </figure>
            </div>
          )}
          <p className="small muted center">
            Both views: 3.84 km across on a 60 m grid, light from the north-west at 45°, no vertical exaggeration. Every
            patch image uses the same contrast stretch, so brightness and texture compare directly between the two
            views. Scale bars are 1 km.
          </p>
        </section>

        <div className="site-grid">
          <section className="card" aria-labelledby="why">
            <h2 id="why">Why it matches</h2>
            <ScoreBars scores={m.sub_scores} />
            <p className="small muted">
              Bars: how close this pair is compared with random pairs of Earth patches from different regions (100 =
              closer than all; the tick marks 75). The score combines 60% terrain fingerprint (
              {(m.s_morph * 100).toFixed(0)}) and 40% image embedding ({(m.s_embed * 100).toFixed(0)}), averaged over the
              three best-matching target patches.
            </p>
            <div className="reason-block good">
              <h3>
                <span className="reason-icon" aria-hidden="true">+</span> Strong match
              </h3>
              <ul>{m.strong_match.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
            <div className="reason-block bad">
              <h3>
                <span className="reason-icon" aria-hidden="true">!</span> Breaks down
              </h3>
              <ul>{m.breaks_down.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
            <div className="reason-block test">
              <h3>
                <span className="reason-icon" aria-hidden="true">▸</span> What you could test here
              </h3>
              {m.tests_suited.length ? (
                <ul className="test-chips">{m.tests_suited.map((s) => <li key={s}>{s}</li>)}</ul>
              ) : (
                <p>None of our test rules fire for this site.</p>
              )}
              <p className="small muted">Test suggestions come from simple rules on our own scores; they are not engineering limits.</p>
            </div>
          </section>

          <section className="card" aria-labelledby="numbers">
            <h2 id="numbers">Terrain, side by side</h2>
            <div className="table-scroll">
              <table className="terrain-table">
                <thead>
                  <tr>
                    <th scope="col">Measure</th>
                    <th scope="col">
                      <i className={`dot dot-${target.body}`} aria-hidden="true" /> {body} target
                    </th>
                    <th scope="col">
                      <i className="dot dot-earth" aria-hidden="true" /> Earth site
                    </th>
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
            </div>

            <h2>Environment at the Earth site</h2>
            {env ? (
              <dl className="env-tiles">
                {envTiles.map((e) => (
                  <div className="stat" key={e.label}>
                    <dt className="stat-label">{e.label}</dt>
                    <dd className="stat-value small-value">{e.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p>Climate and land-cover values have not been computed for this site yet.</p>
            )}
            <p className="small muted">Climate: NASA POWER climatology (2001–2025 monthly means). Land cover: ESA WorldCover 2021.</p>

            <h2>Where it is</h2>
            <SiteInset lat={m.lat} lon={m.lon} sizeKm={3.84} />
            <p className="small muted">Landsat WELD true-colour annual composite (year 2000) from NASA GIBS. The box marks the matched 3.84 km patch.</p>
          </section>
        </div>

        <LightingPanel m={m} target={target} info={linfo.data} />
        {m.calendar && <CalendarStrip m={m} target={target} info={linfo.data} />}

        <section className="before-you-go card" aria-labelledby="byg">
          <h2 id="byg">Before you go</h2>
          <p>
            Before any field work, check land status and access, permits, safety, and the wishes of local and Indigenous
            communities.
          </p>
          {(regions.data?.find((r) => r.id === m.region_id)?.before_you_go ?? []).map((n) => (
            <p key={n.source_url} className="small">
              {n.text} <a href={n.source_url}>Source</a>
            </p>
          ))}
        </section>

        <section className="limits" aria-labelledby="limits">
          <h2 id="limits">What Earth cannot reproduce</h2>
          <p>
            Terrain shape is only one part of an analog. No place on Earth reproduces {target.body === 'moon' ? 'the Moon’s gravity, vacuum' : 'Mars’ gravity, thin carbon-dioxide air'},
            radiation, regolith or mineralogy, and a 60 m grid cannot see boulders or small craters. Use these sites for
            the tests the terrain supports, and check everything else separately.
          </p>
        </section>

        <nav className="site-nav" aria-label="Other candidate sites">
          {prev ? <Link className="btn btn-ghost" to={`/site/${targetId}/${encodeURIComponent(prev.site_id)}`}>← #{prev.rank} {prev.region_name}</Link> : <span />}
          <Link className="btn btn-ghost" to={`/brief/${targetId}/${encodeURIComponent(m.site_id)}`}>
            Field-test brief (print)
          </Link>
          <button type="button" className="btn btn-primary" onClick={() => download(`rehearsal-grounds_${targetId}_rank${m.rank}.md`, dossierMarkdown(target, m))}>
            Download dossier (Markdown)
          </button>
          {next ? <Link className="btn btn-ghost" to={`/site/${targetId}/${encodeURIComponent(next.site_id)}`}>#{next.rank} {next.region_name} →</Link> : <span />}
        </nav>
      </div>
    </article>
  )
}
