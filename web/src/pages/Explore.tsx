import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import LoadState from '../components/LoadState.tsx'
import WorldMap from '../components/WorldMap.tsx'
import { bodyLabel, dataUrl, fmt, useJson } from '../data.ts'
import type { Match, Results, SubScores, Target } from '../types.ts'

type Filter = 'all' | 'less_studied' | 'well_studied'
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'less_studied', label: 'Outside our analog catalogue' },
  { id: 'well_studied', label: 'Near a known analog' },
]
const SHOWN = 20
const DEFAULT_TARGET = 'moon_site23_malapert'
const PRIORITY_KEYS: { key: keyof SubScores; label: string }[] = [
  { key: 'relief', label: 'Relief' },
  { key: 'slope', label: 'Slope' },
  { key: 'roughness', label: 'Roughness' },
  { key: 'shape', label: 'Shape' },
  { key: 'embedding', label: 'Image look-alike' },
]
const EQUAL: Record<keyof SubScores, number> = { relief: 1, slope: 1, roughness: 1, shape: 1, embedding: 1 }

/** Weighted mean of the explanation bars with the planner's own weights. */
function priorityScore(m: Match, w: Record<keyof SubScores, number>): number {
  const total = PRIORITY_KEYS.reduce((a, { key }) => a + w[key], 0)
  if (total === 0) return 0
  return PRIORITY_KEYS.reduce((a, { key }) => a + w[key] * m.sub_scores[key], 0) / total
}

function PriorityPanel({ weights, onChange }: { weights: Record<keyof SubScores, number>; onChange: (w: Record<keyof SubScores, number>) => void }) {
  return (
    <details className="priorities">
      <summary>Re-rank the shortlist by your priorities</summary>
      <p className="small muted">
        Weights apply to the explanation bars of the 50 shortlisted sites (0 = ignore, 3 = most important). The
        similarity search itself is unchanged; this only reorders its shortlist.
      </p>
      <div className="priority-grid">
        {PRIORITY_KEYS.map(({ key, label }) => (
          <label key={key}>
            <span>
              {label} <strong>{weights[key]}</strong>
            </span>
            <input
              type="range"
              min={0}
              max={3}
              step={1}
              value={weights[key]}
              onChange={(e) => onChange({ ...weights, [key]: Number(e.target.value) })}
            />
          </label>
        ))}
      </div>
      <button type="button" onClick={() => onChange(EQUAL)}>
        Reset to similarity ranking
      </button>
    </details>
  )
}

export function regionSetLabel(set: string): string {
  if (set === 'well_studied') return 'Region: a well-studied analog area'
  if (set === 'discovery') return 'Region: discovery candidate'
  return 'Region: crater benchmark tile'
}

export function noveltyLabel(status: 'well_studied' | 'less_studied'): string {
  return status === 'less_studied' ? 'Outside our analog catalogue' : 'Near a known analog'
}

export function NoveltyBadge({ m }: { m: Match }) {
  if (!m.novelty) return <span className="badge badge-pending">novelty pending</span>
  return m.novelty.status === 'less_studied' ? (
    <span className="badge badge-less">{noveltyLabel('less_studied')}</span>
  ) : (
    <span className="badge badge-well">{noveltyLabel('well_studied')}</span>
  )
}

function TargetPicker({ targets, current, onPick }: { targets: Target[]; current: string; onPick: (id: string) => void }) {
  return (
    <div className="target-picker" role="group" aria-label="Choose a Moon or Mars target site">
      {targets.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`target-option body-${t.body}`}
          aria-pressed={t.id === current}
          onClick={() => onPick(t.id)}
        >
          <img src={dataUrl(t.hillshade_png)} alt="" width={56} height={56} />
          <span className="target-option-text">
            <span className="target-body">{bodyLabel(t.body)}</span>
            <span className="target-name">{t.name}</span>
          </span>
        </button>
      ))}
    </div>
  )
}

export default function Explore() {
  const [params, setParams] = useSearchParams()
  const targets = useJson<Target[]>('targets.json')
  const targetId = params.get('target') ?? DEFAULT_TARGET
  const filter = (params.get('filter') as Filter) || 'all'
  const results = useJson<Results>(`results/${targetId}.json`)
  const [selected, setSelected] = useState<string | null>(null)
  const [weights, setWeights] = useState<Record<keyof SubScores, number>>(EQUAL)
  const custom = PRIORITY_KEYS.some(({ key }) => weights[key] !== 1)
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())

  const target = targets.data?.find((t) => t.id === targetId) ?? null
  const hasNovelty = !!results.data?.matches.some((m) => m.novelty)
  const shown = useMemo(() => {
    const all = results.data?.matches ?? []
    const filtered = filter === 'all' || !hasNovelty ? all : all.filter((m) => m.novelty?.status === filter)
    const ordered = custom
      ? [...filtered].sort((a, b) => priorityScore(b, weights) - priorityScore(a, weights) || a.rank - b.rank)
      : filtered
    return ordered.slice(0, SHOWN)
  }, [results.data, filter, hasNovelty, custom, weights])

  useEffect(() => {
    setSelected(shown[0]?.site_id ?? null)
  }, [shown])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    next.set(key, value)
    setParams(next, { replace: true })
  }

  const select = useCallback((siteId: string, focus = false) => {
    setSelected(siteId)
    const el = itemRefs.current.get(siteId)
    if (el) {
      el.scrollIntoView({ block: 'nearest' })
      if (focus) el.focus()
    }
  }, [])

  const onListKey = (e: KeyboardEvent<HTMLOListElement>) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    e.preventDefault()
    const i = shown.findIndex((m) => m.site_id === selected)
    const j = e.key === 'ArrowDown' ? Math.min(shown.length - 1, i + 1) : Math.max(0, i - 1)
    if (shown[j]) select(shown[j].site_id, true)
  }

  return (
    <div className="page explore">
      <section className="intro">
        <h1>Where on Earth should a team rehearse for a specific Moon or Mars site?</h1>
        <p className="lede">
          Pick a target. Rehearsal Grounds compares its terrain, patch by patch on a 60 m grid, with {''}
          thousands of 3.84 km patches of Earth, then explains each candidate analog: what matches, where the
          analogy breaks down, and what you could test there.
        </p>
      </section>

      <LoadState what="targets" error={targets.error} loading={targets.loading} retry={targets.retry} />
      {targets.data && <TargetPicker targets={targets.data} current={targetId} onPick={(id) => update('target', id)} />}

      {target && (
        <section className={`target-summary body-${target.body}`} aria-label="Selected target">
          <img
            className="target-hillshade"
            src={dataUrl(target.hillshade_png)}
            alt={`Shaded relief of the ${target.name} target terrain model, ${target.extent_km.toFixed(0)} km across`}
            width={160}
            height={160}
          />
          <div>
            <h2>
              {target.name} <span className="muted">· {bodyLabel(target.body)}</span>
            </h2>
            <p>{target.description}</p>
            <p className="small">
              {target.n_patches} patches of 3.84 km on a {target.resolution_m} m grid ·{' '}
              <a href={target.description_source_url}>source</a> · <a href={target.source_url}>data product</a>
            </p>
            {results.data && (
              <p className="small coverage">
                Earth has a close terrain match (closer than 90% of random Earth pairs) for{' '}
                <strong>{(results.data.target_coverage.share_close_90 * 100).toFixed(0)}%</strong> of this target’s
                patches.
                {results.data.target_coverage.share_close_90 < 0.95 &&
                  ' The rest, mostly the steepest slopes, have no close match among the indexed regions.'}
              </p>
            )}
          </div>
        </section>
      )}

      <section className="results-layout" aria-label="Candidate analog sites">
        <div className="results-panel">
          <div className="results-head">
            <h2>Top candidate analogs</h2>
            <div className="segmented" role="group" aria-label="Filter by distance to a known analog">
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  aria-pressed={filter === f.id}
                  disabled={!hasNovelty && f.id !== 'all'}
                  onClick={() => update('filter', f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <PriorityPanel weights={weights} onChange={setWeights} />
          <p className="small muted">
            Similarity score (0–100) · showing {shown.length} of {results.data?.matches.length ?? 0} sites kept at
            least 10 km apart{custom ? ', reordered by your priorities (numbers are the original ranks)' : ''}. Use ↑ ↓
            to move through the list.
          </p>
          <LoadState what="results" error={results.error} loading={results.loading} retry={results.retry} />
          <ol className="results-list" onKeyDown={onListKey}>
            {shown.map((m) => (
              <li key={m.site_id} className={m.site_id === selected ? 'is-selected' : ''}>
                <button
                  type="button"
                  className="result-select"
                  ref={(el) => {
                    if (el) itemRefs.current.set(m.site_id, el)
                    else itemRefs.current.delete(m.site_id)
                  }}
                  aria-current={m.site_id === selected ? 'true' : undefined}
                  onClick={() => select(m.site_id)}
                  onFocus={() => setSelected(m.site_id)}
                >
                  <span className="rank">{m.rank}</span>
                  <span className="result-main">
                    <span className="result-name">{m.region_name}</span>
                    <span className="result-meta">
                      <NoveltyBadge m={m} />
                      {m.novelty && (
                        <span className="muted">
                          {' '}
                          {fmt(m.novelty.distance_km, 0)} km from {m.novelty.nearest_known_analog}
                        </span>
                      )}
                      <span className="region-set">{regionSetLabel(m.region_set)}</span>
                    </span>
                  </span>
                  <span className="result-score" aria-label={`similarity score ${m.score.toFixed(1)}`}>
                    {m.score.toFixed(1)}
                    {custom && <span className="priority-score">priority {priorityScore(m, weights).toFixed(0)}</span>}
                  </span>
                </button>
                <Link className="result-open" to={`/site/${targetId}/${encodeURIComponent(m.site_id)}`}>
                  Dossier<span className="visually-hidden"> for #{m.rank} {m.region_name}</span> →
                </Link>
              </li>
            ))}
          </ol>
          {results.data && shown.length === 0 && <p>No sites match this filter.</p>}
        </div>
        <div className="map-panel">
          <WorldMap matches={shown} selected={selected} onSelect={(id) => select(id)} fitKey={`${targetId}|${filter}`} />
          <p className="map-legend small">
            <span className="pin pin-less_studied legend-pin">1</span> outside our analog catalogue (more than 50 km
            from every catalogued analog and not in a well-studied analog region){' '}
            <span className="pin pin-well_studied legend-pin">1</span> near a known analog · numbers are ranks
          </p>
        </div>
      </section>
    </div>
  )
}
