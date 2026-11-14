import type { SubScores } from '../types.ts'

const LABELS: { key: keyof SubScores; label: string; hint: string }[] = [
  { key: 'relief', label: 'Relief', hint: 'height range and hypsometry' },
  { key: 'slope', label: 'Slope', hint: 'slope statistics at 60 m and 120 m' },
  { key: 'roughness', label: 'Roughness', hint: 'plane-fit spread and ruggedness' },
  { key: 'shape', label: 'Shape', hint: 'curvature and bowl index' },
  { key: 'embedding', label: 'Image embedding', hint: 'ResNet-18 view of the shaded relief' },
]
const WEAK = 75

/**
 * Five explanation meters. Each prints its number, and a weak bar (under 75) also
 * says "weak" in text, so colour is never the only cue.
 */
export default function ScoreBars({ scores, compact = false }: { scores: SubScores; compact?: boolean }) {
  return (
    <dl className={`bars${compact ? ' bars-compact' : ''}`}>
      {LABELS.map(({ key, label, hint }) => {
        const v = scores[key]
        const weak = v < WEAK
        return (
          <div className={`bar-row${weak ? ' is-weak' : ''}`} key={key}>
            <dt>
              {label}
              {!compact && <span className="hint">{hint}</span>}
            </dt>
            <dd>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
                <span className="bar-tick" style={{ left: `${WEAK}%` }} />
              </span>
              <span className="bar-value">
                {v.toFixed(0)}
                {weak && <span className="bar-flag">weak</span>}
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
