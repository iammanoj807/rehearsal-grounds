import { fmt } from '../data.ts'
import { monthNames } from '../exportShortlist.ts'
import type { LightingInfo, Match, Target } from '../types.ts'

const MONTH = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** Low-sun shadow comparison: its own panel, never part of the similarity score. */
export default function LightingPanel({ m, target, info }: { m: Match; target: Target; info: LightingInfo | null }) {
  const band = target.sun_band
  return (
    <section className="lighting card" aria-labelledby="lighting-title">
      <div className="lighting-head">
        <div>
          <p className="eyebrow">Low-sun lighting analog</p>
          <h2 id="lighting-title">Do the shadows behave alike?</h2>
        </div>
        {m.lighting && band ? (
          <div className="lighting-score" aria-label={`lighting similarity ${m.lighting.similarity.toFixed(0)} out of 100`}>
            <span className="lighting-number">{m.lighting.similarity.toFixed(1)}</span>
            <span className="score-label">lighting similarity / 100</span>
          </div>
        ) : null}
      </div>
      {!band || !m.lighting ? (
        <p className="muted">
          Not applicable: {target.name} is not a low-sun site. The polar low-Sun comparison is computed for the Moon’s
          south-pole targets only.
        </p>
      ) : (
        <>
          <p>
            At {Math.abs(band.latitude_deg).toFixed(1)}° S the noon Sun at {target.name} stays between{' '}
            <strong>{band.low_deg.toFixed(1)}°</strong> and <strong>{band.high_deg.toFixed(1)}°</strong> above the horizon
            all year (the Moon’s axis is tilted about 1.54°). For each Sun elevation we march rays toward the Sun from
            36 directions and count the share of the 3.84 km patch in shadow, cast or attached, with the body’s
            curvature included. The score compares the two shadow shares at the elevations inside the band (
            {m.lighting.elevations.map((e) => `${e}°`).join(', ')}). It is a separate panel and never changes the
            similarity score.
          </p>
          <div className="table-scroll">
            <table className="metric-table shadow-table">
              <thead>
                <tr>
                  <th scope="col">Sun elevation</th>
                  {m.lighting.shadow.map((s) => (
                    <th key={s.elevation_deg} scope="col" className={m.lighting!.elevations.includes(s.elevation_deg) ? 'in-band' : ''}>
                      {s.elevation_deg}°{m.lighting!.elevations.includes(s.elevation_deg) ? ' ●' : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">
                    <i className={`dot dot-${target.body}`} aria-hidden="true" /> {target.name} in shadow
                  </th>
                  {m.lighting.shadow.map((s) => (
                    <td key={s.elevation_deg}>{(s.target * 100).toFixed(0)}%</td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">
                    <i className="dot dot-earth" aria-hidden="true" /> {m.region_name} in shadow
                  </th>
                  {m.lighting.shadow.map((s) => (
                    <td key={s.elevation_deg}>{(s.earth * 100).toFixed(0)}%</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="small muted">
            ● inside the target’s Sun band. At 1–2° most rough terrain is largely in shadow on both bodies, so scores
            bunch near the top; read the shadow shares, not only the score. The Earth patch is given the same visible
            surroundings as the target patch, whose map may end nearby. Our choices: elevations {info?.settings.elevations_deg ? String(info.settings.elevations_deg) : '1, 2, 3, 5, 10'}°,
            36 azimuths, 3.84 km of surrounding terrain.
            {(m.lighting.edge_limited_target || m.lighting.edge_limited_earth) &&
              ` Edge-limited: the surrounding terrain is cut off by the edge of the ${[
                m.lighting.edge_limited_target ? 'target' : '',
                m.lighting.edge_limited_earth ? 'Earth' : '',
              ]
                .filter(Boolean)
                .join(' and ')} map, so some distant shadows may be missing.`}
          </p>
        </>
      )}
    </section>
  )
}

/** Twelve months of Sun hours and climate at the Earth site, with the suggested months. */
export function CalendarStrip({ m, target, info }: { m: Match; target: Target; info: LightingInfo | null }) {
  const cal = m.calendar ?? []
  const best = new Set(m.best_months ?? [])
  const moon = !!target.sun_band
  const maxLow = Math.max(1, ...cal.map((c) => c.low_sun_h ?? 0))
  return (
    <section className="calendar card" aria-labelledby="calendar-title">
      <p className="eyebrow">Rehearsal window</p>
      <h2 id="calendar-title">When to go</h2>
      {m.best_months && m.best_months.length > 0 && (
        <p className="best-months">
          Best months: <strong>{monthNames(m.best_months)}</strong>
          <span className="muted small"> · {m.best_months_rule} Our rules, not safety advice.</span>
        </p>
      )}
      <div className="table-scroll">
        <table className="metric-table calendar-table">
          <thead>
            <tr>
              <th scope="col">Month</th>
              {cal.map((c) => (
                <th key={c.month} scope="col" className={best.has(c.month) ? 'is-best' : ''} title={MONTH_LONG[c.month - 1]}>
                  {MONTH[c.month - 1]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {moon && (
              <tr>
                <th scope="row">Low-sun hours / day</th>
                {cal.map((c) => (
                  <td key={c.month} className={best.has(c.month) ? 'is-best' : ''}>
                    <span className="cal-bar" aria-hidden="true">
                      <span style={{ height: `${((c.low_sun_h ?? 0) / maxLow) * 100}%` }} />
                    </span>
                    {fmt(c.low_sun_h, 1)}
                  </td>
                ))}
              </tr>
            )}
            <tr>
              <th scope="row">Daylight hours</th>
              {cal.map((c) => (
                <td key={c.month} className={best.has(c.month) ? 'is-best' : ''}>{fmt(c.daylight_h, 1)}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">Min / max °C</th>
              {cal.map((c) => (
                <td key={c.month} className={best.has(c.month) ? 'is-best' : ''}>
                  {fmt(c.t2m_min_c, 0)}/{fmt(c.t2m_max_c, 0)}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row">Rain mm/day</th>
              {cal.map((c) => (
                <td key={c.month} className={best.has(c.month) ? 'is-best' : ''}>{fmt(c.precip_mm_per_day, 1)}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="small muted">
        {moon
          ? `Low-sun hours: daylight with the true Sun between 0° and ${target.sun_band!.high_deg.toFixed(1)}° (the top of the target's band), on the 15th of each month, 5-minute steps. `
          : 'Daylight hours on the 15th of each month, 5-minute steps. '}
        Temperatures and rain: NASA POWER monthly climatology (2001–2025).{' '}
        {info && (
          <>
            {info.refraction_note} <a href={info.refraction_source_url}>NOAA</a>
          </>
        )}
      </p>
    </section>
  )
}
