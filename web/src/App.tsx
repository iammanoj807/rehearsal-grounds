import { useEffect } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Explore from './pages/Explore.tsx'
import SitePage from './pages/Site.tsx'
import ValidationPage from './pages/Validation.tsx'
import About from './pages/About.tsx'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <ScrollToTop />
      <header className="site-header">
        <NavLink to="/" className="wordmark" aria-label="Rehearsal Grounds, home">
          <span className="wordmark-mark" aria-hidden="true" />
          <span>
            Rehearsal <em>Grounds</em>
          </span>
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Explore
          </NavLink>
          <NavLink to="/validation">Validation</NavLink>
          <NavLink to="/about">About &amp; data</NavLink>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Explore />} />
          <Route path="/site/:targetId/:siteId" element={<SitePage />} />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/about" element={<About />} />
          <Route
            path="*"
            element={
              <section className="page narrow">
                <h1>Page not found</h1>
                <p>
                  <NavLink to="/">Back to Explore</NavLink>
                </p>
              </section>
            }
          />
        </Routes>
      </main>
      <footer className="site-footer">
        <p className="footer-mark mono">Rehearsal Grounds · Moon ↔ Earth ↔ Mars · 60 m terrain analogs</p>
        <p>
          Rehearsal Grounds · 2026 NASA Space Apps Challenge · Data: NASA (LRO LOLA via PGDA, POWER, GIBS), USGS
          Astrogeology, ESA Copernicus DEM and WorldCover. Scores are similarity scores for candidate analogs, not
          certifications.
        </p>
      </footer>
    </>
  )
}
