import type { Match, SunBand } from './types.ts'

const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "The noon Sun stays between A and B", or the honest version when the Sun dips below the horizon. */
export function bandSentence(name: string, band: SunBand): string {
  const lat = `${Math.abs(band.latitude_deg).toFixed(1)}° S`
  if (band.low_deg <= 0) {
    return `At ${lat}, the Sun at ${name} never rises more than ${band.high_deg.toFixed(1)}° above the horizon, and for part of the year it stays below it`
  }
  return `At ${lat}, the noon Sun at ${name} stays between ${band.low_deg.toFixed(1)}° and ${band.high_deg.toFixed(1)}° above the horizon all year`
}

/** "45 min" or "2 h 10 min". */
export function duration(min: number): string {
  if (min < 60) return `${Math.round(min)} min`
  const h = Math.floor(min / 60)
  const m = Math.round(min - 60 * h)
  return m ? `${h} h ${m} min` : `${h} h`
}

/** The month with the most low-sun time at a site, from its calendar. */
export function peakLowSun(m: Match): { min: number; month: string } | null {
  const cal = (m.calendar ?? []).filter((c) => c.low_sun_h != null)
  if (!cal.length) return null
  const best = cal.reduce((a, b) => ((b.low_sun_h ?? 0) > (a.low_sun_h ?? 0) ? b : a))
  return { min: 60 * (best.low_sun_h ?? 0), month: MONTH_LONG[best.month - 1] }
}

/** Typical low-sun minutes a day at the JETT5 area for this target's band (median of the 12 months). */
export function jett5Typical(band: SunBand): number | null {
  const v = band.jett5_low_sun_min
  if (!v || v.length !== 12) return null
  const s = [...v].sort((a, b) => a - b)
  return (s[5] + s[6]) / 2
}
