import type { SubScores } from '../types.ts'

const LABELS: { key: keyof SubScores; label: string; hint: string }[] = [
  { key: 'relief', label: 'Relief', hint: 'height range and hypsometry' },
  { key: 'slope', label: 'Slope', hint: 'slope statistics at 60 m and 120 m' },
  { key: 'roughness', label: 'Roughness', hint: 'plane-fit spread and ruggedness' },
  { key: 'shape', label: 'Shape', hint: 'curvature and bowl index' },
  { key: 'embedding', label: 'Image embedding', hint: 'ResNet-18 view of the shaded relief' },
]

/** Five explanation bars, each with its number so colour is never the only cue. */
export default function ScoreBars({ scores }: { scores: SubScores }) {
  return (
    <dl className="bars">
      {LABELS.map(({ key, label, hint }) => {
        const v = scores[key]
        return (
          <div className="bar-row" key={key}>
            <dt>
              {label} <span className="hint">{hint}</span>
            </dt>
            <dd>
              <span className="bar-track" aria-hidden="true">
                <span className={`bar-fill${v < 75 ? ' low' : ''}`} style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
              </span>
              <span className="bar-value">{v.toFixed(0)}</span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
