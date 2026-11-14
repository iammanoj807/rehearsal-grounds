import LoadState from '../components/LoadState.tsx'
import { useJson } from '../data.ts'
import type { Meta, Sources } from '../types.ts'

export default function About() {
  const sources = useJson<Sources>('sources.json')
  const meta = useJson<Meta>('meta.json')
  return (
    <article className="page narrow about">
      <p className="eyebrow">About &amp; data</p>
      <h1>About Rehearsal Grounds</h1>
      <p className="lede">
        Before astronauts and rovers work at the Moon’s south pole or in Jezero crater on Mars, teams rehearse on
        Earth. Rehearsal Grounds helps an analog field-test planner choose where, by matching terrain at the scale of a
        crater rim, ridge or lava field (about 60 m), not at the scale of a whole region.
      </p>

      <h2>How it works</h2>
      <ol className="steps">
        <li>
          <strong>Real terrain models.</strong> NASA LRO LOLA 5 m site maps for the Moon, the USGS CTX terrain model
          of Jezero for Mars, and ESA Copernicus 30 m elevation for{' '}
          {meta.data ? meta.data.n_earth_patches.toLocaleString('en-GB') : 'tens of thousands of'} Earth patches in
          30 regions.
        </li>
        <li>
          <strong>One common grid.</strong> Everything is resampled to 60 m in a local metric projection (Mars is
          warped to an equidistant projection centred on Jezero), then cut into 3.84 km patches that overlap by half.
        </li>
        <li>
          <strong>Terrain fingerprints.</strong> Each patch gets 20 rotation-invariant numbers a geologist can read:
          relief, slope statistics, roughness, curvature and a bowl-versus-dome index. A pretrained ResNet-18 adds an
          image embedding of the shaded relief.
        </li>
        <li>
          <strong>Search with environment filters.</strong> Earth patches with more than 20% vegetation (trees, shrubs,
          grass, moss, wetland), cropland or buildings, more than 5% water, more than 50% snow and ice, or almost no
          relief are left out. Antarctica has no land-cover data, so its sites carry a warning instead. Every remaining patch is scored against every target
          patch; sites are kept at least 10 km apart.
        </li>
        <li>
          <strong>Explain and validate.</strong> Each site shows its feature-by-feature comparison, climate from NASA
          POWER, land cover from ESA WorldCover, a novelty flag, and the tests it suits. The method is checked on a
          crater retrieval benchmark (see Validation).
        </li>
      </ol>

      <h2>What the scores mean</h2>
      <p>
        The similarity score (0–100) is 100 × (0.6 × terrain similarity + 0.4 × image similarity). Terrain similarity
        is exp(−d²/2σ²), where d is the distance between the two fingerprints with equal weight for the relief, slope,
        roughness and shape groups. σ is the median distance from the target’s patches to their nearest Earth patch,
        so the score adapts to how unusual the target is. It is a similarity score, not an accuracy or a certification.
      </p>
      <p>
        Our crater test shows a division of labour: at 60 m the image embedding does most of the landform recognition,
        and the terrain numbers explain each match in units a geologist can check. See the Validation page.
      </p>

      <h2>What Earth cannot reproduce</h2>
      <ul>
        <li>Gravity: Earth’s is about six times the Moon’s and about 2.6 times that of Mars.</li>
        <li>Air: the Moon has none and Mars has less than 1% of Earth’s surface pressure.</li>
        <li>Radiation, regolith and mineralogy: none of these are visible in a terrain model.</li>
        <li>Polar light: low Sun angles and permanently shadowed craters at the lunar south pole.</li>
        <li>Scale: a 60 m grid cannot see boulders, small craters or surface texture.</li>
        <li>Gravity also shapes landforms: craters and slopes of the same size formed differently on each body.</li>
      </ul>

      <h2>Data and licences</h2>
      <LoadState what="data sources" error={sources.error} loading={sources.loading} retry={sources.retry} />
      {sources.data && (
        <ul className="datasets">
          {sources.data.datasets.map((d) => (
            <li key={d.id}>
              <p>
                <a href={d.url}>
                  <strong>{d.name}</strong>
                </a>{' '}
                · {d.agency}
              </p>
              <p className="small">Used for: {d.used_for}</p>
              <p className="small">
                Licence: {d.licence}
                {d.downloaded ? ` · downloaded ${d.downloaded.slice(0, 10)}` : ''}
              </p>
              <p className="small muted">{d.attribution}</p>
              {d.citation && <p className="small muted">{d.citation}</p>}
            </li>
          ))}
        </ul>
      )}

      <h2>Team</h2>
      <p>Rehearsal Grounds · Manoj Kumar Thapa · 2026 NASA Space Apps Challenge, “Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars”.</p>
      {meta.data && (
        <p className="small muted">
          Data build {meta.data.generated_at} · configuration {meta.data.config_hash.slice(0, 12)}
        </p>
      )}
    </article>
  )
}
