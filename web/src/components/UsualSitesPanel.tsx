import type { Match, UsualSites } from '../types.ts'

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
export default function UsualSitesPanel({ data, targetId, matches }: { data: UsualSites; targetId: string; matches: Match[] }) {
  const t = data.targets[targetId]
  if (!t) return null
  const ft = data.field_test
  const byId = new Map(matches.map((m) => [m.site_id, m]))
  const rows = t.regions
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
        </div>
      )}
    </section>
  )
}
