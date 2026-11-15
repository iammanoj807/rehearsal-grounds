import { duration, jett5Typical, peakLowSun } from '../lowSun.ts'
import type { Match, Target, UsualRegion, UsualSites } from '../types.ts'

const GROUP_LABEL: Record<string, string> = {
  relief: 'relief',
  slope: 'slope',
  roughness: 'roughness',
  shape: 'shape',
  embedding: 'image embedding',
}

/**
 * How the usual analog sites score for this target, on the app's own similarity
 * score, and which shortlisted sites are a closer terrain match on our fingerprint
 * than the area of NASA's JETT5 field test.
 */
function RegionRows({ rows }: { rows: UsualRegion[] }) {
  return (
    <div className="table-scroll">
      <table className="metric-table usual-table">
        <thead>
          <tr>
            <th scope="col">Region</th>
            <th scope="col">Best score</th>
            <th scope="col">Rank</th>
            <th scope="col">Rank, masks off</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.region_id} className={r.field_test ? 'is-headline' : ''}>
              <th scope="row">
                {r.name}
                {r.field_test && <span className="badge badge-field">NASA’s 2024 Artemis III field test area</span>}
              </th>
              <td>{r.best_score != null ? r.best_score.toFixed(1) : '–'}</td>
              <td>{r.rank != null ? `#${r.rank.toLocaleString('en-GB')}` : 'all masked'}</td>
              <td>
                #{r.rank_masks_off.toLocaleString('en-GB')}
                {r.best_patch_masked && <span className="masked-note"> · best patch masked</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function UsualSitesPanel({ data, targetId, matches, target }: { data: UsualSites; targetId: string; matches: Match[]; target: Target }) {
  const t = data.targets[targetId]
  if (!t) return null
  const ft = data.field_test
  const byId = new Map(matches.map((m) => [m.site_id, m]))
  const rows = t.regions
  const band = target.sun_band
  const typical = band ? jett5Typical(band) : null
  const peaks = matches
    .map((m) => ({ m, p: peakLowSun(m) }))
    .filter((x): x is { m: Match; p: { min: number; month: string } } => x.p != null)
  const most = peaks.length ? peaks.reduce((a, b) => (b.p.min > a.p.min ? b : a)) : null
  const lowSun =
    band && typical != null && most ? (
      <p className="jett5-line small">
        <strong>Low Sun:</strong> the JETT5 area gets about {duration(typical)} a day of Sun as low as at {target.name}{' '}
        (0–{band.high_deg.toFixed(1)}°). On this shortlist the most is at {most.m.region_name} (#{most.m.rank}): up to{' '}
        {duration(most.p.min)} a day in {most.p.month}.
      </p>
    ) : null
  return (
    <section className="usual card" aria-labelledby="usual-title">
      <div className="usual-head">
        <div>
          <p className="eyebrow">Context</p>
          <h3 id="usual-title">How the usual analog sites compare</h3>
        </div>
        <p className="small muted">
          Each well-studied region’s best 3.84 km patch for this target, on the same similarity score, ranked among{' '}
          {rows[0]?.n_candidates.toLocaleString('en-GB')} searchable Earth patches. “Masks off” ranks it among all{' '}
          {rows[0]?.n_candidates_masks_off.toLocaleString('en-GB')} Earth patches, including vegetated, wet, icy and flat ones.
        </p>
      </div>
      <RegionRows rows={rows.filter((r) => r.field_test)} />
      {ft && t.field_test && (
        <div className="jett5">
          <p className="small">
            <strong>{ft.name}</strong> ({ft.when}, {ft.where}). {ft.summary} Our SP Crater region lies in that volcanic
            field.{' '}
            {ft.source_urls.map((u, i) => (
              <a key={u} href={u}>
                [{i + 1}]
              </a>
            ))}
          </p>
          {t.field_test.outranked_by.length > 0 ? (
            <>
              <p className="small muted">
                Shortlisted sites with a closer terrain match on our fingerprint than the field-test area’s best patch
                (score {t.field_test.score.toFixed(1)}, rank #{t.field_test.rank.toLocaleString('en-GB')}):
              </p>
              <ol className="outrank">
                {t.field_test.outranked_by.map((o) => (
                  <li key={o.site_id}>
                    <span className="mono">#{o.rank}</span> {byId.get(o.site_id)?.region_name ?? o.region_id}{' '}
                    <strong>{o.score.toFixed(1)}</strong>
                    <span className="muted">
                      {' '}
                      · closer on{' '}
                      {o.closer_groups.length ? o.closer_groups.map((g) => GROUP_LABEL[g] ?? g).join(', ') : 'no single group'}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <p className="small muted">No shortlisted site scores higher than the field-test area’s best patch for this target.</p>
          )}
          {lowSun}
        </div>
      )}
      <details className="usual-all">
        <summary>Show all usual sites ({rows.length})</summary>
        <RegionRows rows={rows} />
      </details>
    </section>
  )
}
