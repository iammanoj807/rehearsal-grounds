import type { Match, Target } from '../types.ts'

/**
 * The slope part of the terrain fingerprint, Moon vs Earth: share of each 60 m patch in each
 * slope band. This is what the score compares (with relief, roughness, shape and the image
 * embedding), so two patches can match here while their ridges sit in different places.
 */
export default function FingerprintChart({ m, target }: { m: Match; target: Target }) {
  const f = m.fingerprint
  if (!f) return null
  const bins = f.slope_bins_deg
  const labels = bins.slice(0, -1).map((b, i) => `${b}–${bins[i + 1]}°`)
  const max = Math.max(...f.target, ...f.earth, 0.01)
  const body = target.body === 'mars' ? 'Mars' : 'Moon'
  return (
    <figure className="fingerprint" aria-labelledby="fp-title">
      <figcaption>
        <p id="fp-title" className="fp-title">
          Slope fingerprint: <strong>{(f.overlap * 100).toFixed(0)}%</strong> of the two slope distributions overlap
        </p>
        <p className="fp-legend small">
          <span><i className={`dot dot-${target.body}`} aria-hidden="true" /> {body} patch</span>
          <span><i className="dot dot-earth" aria-hidden="true" /> Earth patch</span>
          <span className="muted">share of the 3.84 km patch in each slope band, 60 m grid</span>
        </p>
      </figcaption>
      <div className="fp-plot" aria-hidden="true">
        {labels.map((lab, i) => (
          <div className="fp-group" key={lab}>
            <div className="fp-bars">
              <span
                className={`fp-bar fp-${target.body}`}
                style={{ height: `${(f.target[i] / max) * 100}%` }}
                title={`${body}, ${lab}: ${(f.target[i] * 100).toFixed(0)}%`}
              />
              <span
                className="fp-bar fp-earth"
                style={{ height: `${(f.earth[i] / max) * 100}%` }}
                title={`Earth, ${lab}: ${(f.earth[i] * 100).toFixed(0)}%`}
              />
            </div>
            <span className="fp-label">{lab}</span>
          </div>
        ))}
      </div>
      <table className="visually-hidden">
        <caption>Share of each patch in each slope band</caption>
        <thead>
          <tr>
            <th scope="col">Slope band</th>
            <th scope="col">{body}</th>
            <th scope="col">Earth</th>
          </tr>
        </thead>
        <tbody>
          {labels.map((lab, i) => (
            <tr key={lab}>
              <th scope="row">{lab}</th>
              <td>{(f.target[i] * 100).toFixed(0)}%</td>
              <td>{(f.earth[i] * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
