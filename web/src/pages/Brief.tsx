import { Link, useParams } from 'react-router-dom'
import LoadState from '../components/LoadState.tsx'
import { bodyLabel, dataUrl, latLon, useJson } from '../data.ts'
import { ATTRIBUTION, monthNames } from '../exportShortlist.ts'
import type { Region, Results, Target } from '../types.ts'

/** One printable page per site: the match, both previews, limits, months and tests. */
export default function BriefPage() {
  const { targetId = '', siteId = '' } = useParams()
  const targets = useJson<Target[]>('targets.json')
  const results = useJson<Results>(`results/${targetId}.json`)
  const regions = useJson<Region[]>('regions.json')
  const target = targets.data?.find((t) => t.id === targetId)
  const m = results.data?.matches.find((x) => x.site_id === decodeURIComponent(siteId))
  if (!target || !m) {
    return (
      <div className="page">
        <LoadState what="brief" error={targets.error ?? results.error} loading={targets.loading || results.loading} retry={() => { targets.retry(); results.retry() }} />
        {!targets.loading && !results.loading && <p>Site not found.</p>}
      </div>
    )
  }
  const body = bodyLabel(target.body)
  const notes = regions.data?.find((r) => r.id === m.region_id)?.before_you_go ?? []
  return (
    <div className="brief-wrap">
      <p className="no-print brief-actions">
        <Link to={`/site/${targetId}/${encodeURIComponent(m.site_id)}`}>← Back to the dossier</Link>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          Print or save as PDF
        </button>
      </p>
      <article className="brief-sheet">
        <header className="brief-head">
          <div>
            <p className="brief-kicker">Rehearsal Grounds · field-test brief</p>
            <h1>
              {m.region_name} <span>for {target.name}</span>
            </h1>
            <p>
              Candidate analog #{m.rank} · {latLon(m.lat, m.lon)} · {body} target
              {target.artemis_iii_region ? ` · Artemis III candidate region (NASA, Oct 2024)` : ''}
            </p>
          </div>
          <div className="brief-scores">
            <p>
              <strong>{m.score.toFixed(1)}</strong> similarity / 100
            </p>
            {m.lighting && (
              <p>
                <strong>{m.lighting.similarity.toFixed(1)}</strong> low-sun shadows / 100
              </p>
            )}
          </div>
        </header>
        <div className="brief-images">
          <figure>
            <img src={dataUrl(m.images.target_hillshade)} alt={`${target.name} patch`} />
            <figcaption>{body}: {target.name}</figcaption>
          </figure>
          <figure>
            <img src={dataUrl(m.images.earth_hillshade)} alt={`${m.region_name} patch`} />
            <figcaption>Earth: {m.region_name}</figcaption>
          </figure>
          {m.images.lowsun_target && m.images.lowsun_earth && (
            <>
              <figure>
                <img src={dataUrl(m.images.lowsun_target)} alt={`${target.name} patch at low sun`} />
                <figcaption>{body}, low sun {target.sun_band?.preview_elevation_deg.toFixed(1)}°</figcaption>
              </figure>
              <figure>
                <img src={dataUrl(m.images.lowsun_earth)} alt={`${m.region_name} patch at low sun`} />
                <figcaption>Earth, same low sun</figcaption>
              </figure>
            </>
          )}
        </div>
        <p className="brief-fine">All patches 3.84 km across, drawn at 30 m from the original maps (scores use the 60 m grid), light from the north-west, one shared contrast stretch per view type.</p>
        <div className="brief-cols">
          <section>
            <h2>What matches</h2>
            <ul>{m.strong_match.map((s) => <li key={s}>{s}</li>)}</ul>
            <h2>Tests suited</h2>
            {m.tests_suited.length ? <ul>{m.tests_suited.map((s) => <li key={s}>{s}</li>)}</ul> : <p>None of our rules fire.</p>}
            <p className="brief-fine">Our scoring rules, not engineering limits.</p>
          </section>
          <section>
            <h2>Where it breaks down</h2>
            <ul>{m.breaks_down.map((s) => <li key={s}>{s}</li>)}</ul>
            <h2>When to go</h2>
            <p>
              {m.best_months?.length ? <>Best months: <strong>{monthNames(m.best_months)}</strong>. {m.best_months_rule}</> : (m.best_months_rule ?? 'No suggestion.')}{' '}
              Our rules, not safety advice.
            </p>
            <h2>Before you go</h2>
            <p>Check land status and access, permits, safety, and the wishes of local and Indigenous communities.</p>
            {notes.map((n) => (
              <p key={n.source_url} className="brief-fine">
                {n.text} ({n.source_url})
              </p>
            ))}
          </section>
        </div>
        <footer className="brief-foot">
          {ATTRIBUTION} · {window.location.origin}
          {window.location.pathname}#/site/{targetId}/{encodeURIComponent(m.site_id)}
        </footer>
      </article>
    </div>
  )
}
