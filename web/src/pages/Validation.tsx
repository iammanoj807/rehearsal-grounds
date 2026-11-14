import LoadState from '../components/LoadState.tsx'
import { fmt, useJson } from '../data.ts'

interface RankerRow {
  id: string
  label: string
  mean_auc: number
  mrr: number
  hit_at_10: number
  hit_at_50: number
}
interface CraterRow {
  crater: string
  region_id: string
  diameter_km: number
  n_queries: number
  n_positive_patches: number
  auc: Record<string, number>
  first_hit_rank: Record<string, number>
}
interface V1 {
  description: string
  index: string
  combined_note: string
  finding: string
  revision_note: string
  n_craters: number
  n_query_patches: number
  n_positive_patches: number
  n_negatives: number
  rankers: RankerRow[]
  per_crater: CraterRow[]
  masked?: { description: string; n_craters: number; rankers: RankerRow[] }
}
interface V2Region {
  region_id: string
  name: string
  set: string
  best_percentile: number | null
}
interface V2Target {
  well_studied_median: number | null
  discovery_median: number | null
  regions: V2Region[]
}
interface V3 {
  resolution_90m?: { description: string; spearman_top20_regions: Record<string, number> }
  weight_perturbation?: { description: string; mean_stay_top10: Record<string, number> }
}
interface Sanity {
  check: string
  passed: boolean
  detail: string
}
interface ValidationFile {
  generated_at: string
  config_hash: string
  v1_crater_retrieval: V1
  v2_rediscovery: { note: string; targets: Record<string, V2Target>; target_names: Record<string, string> }
  v3_robustness: V3
  v4_sanity: Sanity[]
  limits: string[]
}

function RankerTable({ rows, caption }: { rows: RankerRow[]; caption: string }) {
  return (
    <div className="table-scroll">
    <table className="metric-table">
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Ranker</th>
          <th scope="col">Mean ROC AUC</th>
          <th scope="col">Mean reciprocal rank</th>
          <th scope="col">Hit rate @10</th>
          <th scope="col">Hit rate @50</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className={r.id === 'combined' ? 'is-headline' : ''}>
            <th scope="row">{r.label}</th>
            <td>{fmt(r.mean_auc, 3)}</td>
            <td>{fmt(r.mrr, 3)}</td>
            <td>{fmt(r.hit_at_10 * 100, 0, '%')}</td>
            <td>{fmt(r.hit_at_50 * 100, 0, '%')}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  )
}

export default function ValidationPage() {
  const v = useJson<ValidationFile>('validation.json')
  if (v.error?.startsWith('404')) {
    return (
      <article className="page narrow">
        <h1>Validation</h1>
        <p>The validation run has not been published yet.</p>
      </article>
    )
  }
  if (!v.data) {
    return (
      <article className="page narrow">
        <h1>Validation</h1>
        <LoadState what="validation results" error={v.error} loading={v.loading} retry={v.retry} />
      </article>
    )
  }
  const d = v.data
  const v1 = d.v1_crater_retrieval
  const combined = v1.rankers.find((r) => r.id === 'combined')
  const embedding = v1.rankers.find((r) => r.id === 'embedding')
  const features = v1.rankers.find((r) => r.id === 'features')
  return (
    <article className="page narrow validation">
      <h1>How we tested the method</h1>
      <p className="lede">
        The headline test asks a question with clean ground truth: given one impact crater on Earth, do the fingerprints
        find the other impact craters, on other continents, among {v1.n_negatives.toLocaleString('en-GB')} patches that are
        not craters?
        {combined && embedding && features && (
          <>
            {' '}With the combined score the mean ROC AUC is <strong>{combined.mean_auc.toFixed(3)}</strong> (0.5 is
            chance); the image embedding alone reaches {embedding.mean_auc.toFixed(3)} and puts another crater in the
            top 10 for {(embedding.hit_at_10 * 100).toFixed(0)}% of queries, while the 20 terrain features alone reach{' '}
            {features.mean_auc.toFixed(3)}.
          </>
        )}
      </p>
      <p className="finding">
        <strong>What this tells us.</strong> {v1.finding}
      </p>

      <section aria-labelledby="v1">
        <h2 id="v1">V1 · Crater retrieval benchmark</h2>
        <p>{v1.description}</p>
        <RankerTable
          rows={v1.rankers}
          caption={`${v1.n_craters} query craters, ${v1.n_positive_patches} crater-containing grid patches, ${v1.n_negatives.toLocaleString('en-GB')} negatives. ${v1.index}`}
        />
        <p className="small muted">{v1.combined_note}</p>
        <p className="small muted">
          ROC AUC: chance that a crater patch from another region outranks a non-crater patch. Reciprocal rank: 1 / rank
          of the first other-crater patch. Hit rate @k: share of queries with another crater in the top k.
        </p>
        <div className="table-scroll">
        <table className="metric-table">
          <caption>Per query crater</caption>
          <thead>
            <tr>
              <th scope="col">Query crater</th>
              <th scope="col">Diameter</th>
              <th scope="col">Grid patches containing it</th>
              <th scope="col">AUC features</th>
              <th scope="col">AUC embedding</th>
              <th scope="col">AUC combined</th>
              <th scope="col">First other-crater rank (embedding)</th>
            </tr>
          </thead>
          <tbody>
            {v1.per_crater.map((c) => (
              <tr key={c.crater}>
                <th scope="row">{c.crater}</th>
                <td>{fmt(c.diameter_km, 2, ' km')}</td>
                <td>{c.n_positive_patches}</td>
                <td>{fmt(c.auc.features, 3)}</td>
                <td>{fmt(c.auc.embedding, 3)}</td>
                <td>{fmt(c.auc.combined, 3)}</td>
                <td>{c.first_hit_rank.embedding?.toLocaleString('en-GB') ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        {v1.masked && <RankerTable rows={v1.masked.rankers} caption={v1.masked.description} />}
        <p className="small revision">
          <strong>Revision.</strong> {v1.revision_note}
        </p>
      </section>

      <section aria-labelledby="v2">
        <h2 id="v2">V2 · Do known analogs rank high? (context only)</h2>
        <p>{d.v2_rediscovery.note}</p>
        <table className="metric-table">
          <caption>Median percentile rank of each region’s best patch among all searchable Earth patches</caption>
          <thead>
            <tr>
              <th scope="col">Target</th>
              <th scope="col">Well-studied regions</th>
              <th scope="col">Discovery regions</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(d.v2_rediscovery.targets).map(([tid, t]) => (
              <tr key={tid}>
                <th scope="row">{d.v2_rediscovery.target_names[tid] ?? tid}</th>
                <td>{fmt(t.well_studied_median, 1)}</td>
                <td>{fmt(t.discovery_median, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="v3">
        <h2 id="v3">V3 · Robustness</h2>
        {d.v3_robustness.resolution_90m && (
          <>
            <p>{d.v3_robustness.resolution_90m.description}</p>
            <ul>
              {Object.entries(d.v3_robustness.resolution_90m.spearman_top20_regions).map(([tid, rho]) => (
                <li key={tid}>
                  {d.v2_rediscovery.target_names[tid] ?? tid}: Spearman ρ = {fmt(rho, 2)}
                </li>
              ))}
            </ul>
          </>
        )}
        {d.v3_robustness.weight_perturbation && (
          <>
            <p>{d.v3_robustness.weight_perturbation.description}</p>
            <ul>
              {Object.entries(d.v3_robustness.weight_perturbation.mean_stay_top10).map(([tid, share]) => (
                <li key={tid}>
                  {d.v2_rediscovery.target_names[tid] ?? tid}: top-10 sites stay in the top 10 in {fmt(share * 100, 0, '%')} of draws on average
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-labelledby="v4">
        <h2 id="v4">V4 · Sanity checks</h2>
        <ul className="checks">
          {d.v4_sanity.map((s) => (
            <li key={s.check}>
              <strong>{s.passed ? 'Pass' : 'Fail'}</strong> · {s.check} <span className="muted">({s.detail})</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="limits">
        <h2 id="limits">Limits</h2>
        <ul>
          {d.limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>
      <p className="small muted">
        Every number on this page is read from validation.json, written by pipeline/10_validate.py at {d.generated_at}{' '}
        (configuration {d.config_hash.slice(0, 12)}). Results are never edited by hand.
      </p>
    </article>
  )
}
