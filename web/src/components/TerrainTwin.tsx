import { useState, type CSSProperties } from 'react'

interface Props {
  targetSrc: string
  earthSrc: string
  targetAlt: string
  earthAlt: string
  body: string
  targetName: string
  earthName: string
  size?: 'md' | 'lg'
}

/**
 * Swipe comparison of a Moon or Mars patch and its Earth match.
 *
 * Both hillshades cover the same 3.84 km at the same scale and share one contrast
 * stretch, so dragging the divider compares them like for like. A native range
 * input drives the divider, which keeps it usable with a keyboard and on touch.
 */
export default function TerrainTwin({ targetSrc, earthSrc, targetAlt, earthAlt, body, targetName, earthName, size = 'md' }: Props) {
  const [pos, setPos] = useState(50)
  const bodyName = body === 'mars' ? 'Mars' : 'Moon'
  return (
    <div className={`twin twin-${size} twin-${body}`} style={{ '--pos': `${pos}%` } as CSSProperties}>
      <img className="twin-img" src={targetSrc} alt={targetAlt} width={256} height={256} draggable={false} />
      <img className="twin-img twin-earth" src={earthSrc} alt={earthAlt} width={256} height={256} draggable={false} />
      <span className="twin-tag twin-tag-target" aria-hidden="true">
        <i className={`dot dot-${body}`} />
        {bodyName}
        <span className="twin-tag-name">{targetName}</span>
      </span>
      <span className="twin-tag twin-tag-earth" aria-hidden="true">
        <i className="dot dot-earth" />
        Earth
        <span className="twin-tag-name">{earthName}</span>
      </span>
      <span className="twin-divider" aria-hidden="true">
        <span className="twin-knob" />
      </span>
      <span className="twin-frame" aria-hidden="true" />
      <input
        className="twin-range"
        type="range"
        min={0}
        max={100}
        step={1}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        aria-label={`Swipe between the ${bodyName} patch (left) and the Earth patch (right)`}
        aria-valuetext={`${100 - pos}% Earth patch shown`}
      />
    </div>
  )
}
