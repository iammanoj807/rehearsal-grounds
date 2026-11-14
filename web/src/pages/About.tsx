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
        In May 2024 NASA’s JETT5 field test rehearsed Artemis III moonwalks in Arizona’s San Francisco Volcanic Field,
        and ran some of them at night to test a variety of lighting conditions, because the lighting at the lunar south
        pole is dynamic (<a href="https://www.usgs.gov/centers/astrogeology-science-center/news/artemis-iii-mission-tests-san-francisco-volcanic-field">USGS</a>,{' '}
        <a href="https://svs.gsfc.nasa.gov/14583">NASA</a>). Rehearsal Grounds answers two questions for an analog
        field-test planner: where on Earth does the terrain match a specific Moon or Mars site, patch by patch at about
        60 m; and where and when does the real Sun cast south-pole-like shadows there?
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
          <strong>Search with environment filters.</strong> Earth patches with more than 20% trees, cropland,
          buildings, wetland or mangrove are left out; shrub, grass and moss also count where NASA POWER gives more than
          500 mm of rain a year (the upper bound of semiarid land, USGS), because in drier places that class is mostly bare
          ground between scattered plants. Patches with more than 5% water, more than 50% snow and ice, or almost no
          relief are also left out. Antarctica has no land-cover data, so its sites carry a warning instead. Every remaining patch is scored against every target
          patch; sites are kept at least 10 km apart.
        </li>
        <li>
          <strong>Explain and validate.</strong> Each site shows its feature-by-feature comparison, climate from NASA
          POWER, land cover from ESA WorldCover, a novelty flag, and the tests it suits. The method is checked on a
          crater retrieval benchmark (see Validation).
        </li>
        <li>
          <strong>Low-sun lighting.</strong> For the Moon’s south-pole targets the noon Sun stays a few degrees above
          the horizon all year. For each site we compute the share of the patch in shadow at low Sun elevations, from 36
          directions, with the body’s curvature, for both the target and the Earth patch, and show a separate lighting
          similarity and a low-sun preview.
        </li>
        <li>
          <strong>Rehearsal window.</strong> For every Earth site: daylight and low-sun hours on the 15th of each month
          (NOAA solar-position equations), NASA POWER monthly temperature and rain, and suggested months from a simple,
          stated rule.
        </li>
      </ol>

      <h2>What the scores mean</h2>
      <p>
        The similarity score (0–100) is 100 × (0.6 × terrain similarity + 0.4 × image similarity). Terrain similarity
        is exp(−d²/2σ²), where d is the distance between the two fingerprints with equal weight for the relief, slope,
        roughness and shape groups. σ is the median distance from the target’s patches to their nearest Earth patch,
        so the score adapts to how unusual the target is. It is a similarity score, not an accuracy or a certification.
        The lighting similarity, 100 × (1 − mean difference in shadow share) at the Sun elevations of the target’s band,
        is a separate number and never changes the similarity score.
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
