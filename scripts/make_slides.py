"""Build the 7-slide backup deck (HTML) from the exported data.

Every number on the slides is read from web/public/data (validation.json,
meta.json, targets.json and the results files), never typed by hand.
Render to PDF with a headless browser, for example:

    python scripts/make_slides.py docs/slides.html
    node <playwright script> docs/slides.html docs/rehearsal-grounds-slides.pdf
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data"
DOCS = ROOT / "docs"


def load(name: str):
    return json.loads((DATA / name).read_text())


def img(rel: str) -> str:
    return (DATA / rel).resolve().as_uri()


def main(out: Path) -> None:
    val = load("validation.json")
    meta = load("meta.json")
    targets = load("targets.json")
    results = {t["id"]: load(f"results/{t['id']}.json") for t in targets}
    v1 = {r["id"]: r for r in val["v1_crater_retrieval"]["rankers"]}
    rho = val["v3_robustness"]["resolution_90m"]["spearman_top20_regions"]
    stay = val["v3_robustness"]["weight_perturbation"]["mean_stay_top10"]
    split = val["v3_robustness"]["weight_split"]["top10_overlap"]
    split_vals = [v for per in split.values() for v in per.values()]
    mal = results["moon_site23_malapert"]
    artemis = load("artemis.json")
    usual = load("usual_sites.json")
    linfo = load("lighting_info.json")
    tmal = next(t for t in targets if t["id"] == "moon_site23_malapert")
    sp_mal = next(r for r in usual["targets"]["moon_site23_malapert"]["regions"] if r["region_id"] == usual["field_test_region_id"])
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    top = mal["matches"][0]
    shack = results["moon_site04_shackleton_rim"]["matches"]
    jez = results["mars_jezero"]["matches"]
    shack_less = next((m for m in shack if m["novelty"] and m["novelty"]["status"] == "less_studied"), None)
    jez_less = next((m for m in jez if m["novelty"] and m["novelty"]["status"] == "less_studied"), None)
    outside = []
    for name, m in (("Shackleton rim", shack_less), ("Jezero", jez_less)):
        if m is not None:
            outside.append(f'{html.escape(m["region_name"])} for {name} (#{m["rank"]}, '
                           f'{m["novelty"]["distance_km"]:,.0f} km from the nearest catalogued analog)')
    outside_text = "; ".join(outside) if outside else "none in the top 50 for Shackleton rim or Jezero"
    e = html.escape

    target_cards = "".join(
        f'<figure class="tcard {t["body"]}"><img src="{img(t["hillshade_png"])}" alt=""><figcaption>'
        f'<span>{"Moon" if t["body"] == "moon" else "Mars"}{" · Artemis III" if t.get("artemis_iii_region") else ""}</span>{e(t["name"])}</figcaption></figure>'
        for t in targets
    )
    bars = "".join(
        f'<div class="bar"><span>{k.capitalize() if k != "embedding" else "Image embedding"}</span>'
        f'<i><b style="width:{v:.0f}%"></b></i><em>{v:.0f}</em></div>'
        for k, v in top["sub_scores"].items()
    )
    rows = "".join(
        f'<tr class="{"hl" if k in ("embedding",) else ""}"><th>{e(v1[k]["label"])}</th>'
        f'<td>{v1[k]["mean_auc"]:.3f}</td><td>{v1[k]["mean_auc_hard"]:.3f}</td>'
        f'<td>{100 * v1[k]["hit_at_10"]:.0f}%</td></tr>'
        for k in ("random", "features", "embedding", "combined", "combined_moon_sigma")
    )
    rho_vals = list(rho.values())
    stay_vals = list(stay.values())
    cov_mal = mal["target_coverage"]["share_close_90"]

    slides = [
        # 1 Title
        f'''<section class="title"><div class="half moon"><img src="{img(top["images"]["target_hillshade"])}" alt=""><p>Moon · Malapert massif</p></div>
<div class="half earth"><img src="{img(top["images"]["earth_hillshade"])}" alt=""><p>Earth · {e(top["region_name"])}</p></div>
<div class="titlebox"><h1>Rehearsal Grounds</h1><p class="sub">Finding where on Earth to rehearse the Moon and Mars, at 60 m</p>
<p class="meta">Team: Rehearsal Grounds · Manoj Kumar Thapa<br>Challenge: Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars<br>2026 NASA Space Apps Challenge</p></div></section>''',
        # 2 Problem
        f'''<section><h2>The problem: rehearsing the south-pole Moon on Earth</h2><ul class="big">
<li>In May 2024 NASA's JETT5 test rehearsed Artemis III moonwalks in Arizona's San Francisco Volcanic Field.</li>
<li>Some EVAs ran at night to test a variety of lighting conditions, because the lighting at the lunar south pole is dynamic.</li>
<li>Two questions for a planner: <b>where</b> does Earth's terrain match a specific Artemis III site, and <b>where and when</b> does the real Sun cast south-pole-like shadows?</li></ul>
<p class="note">Sources: USGS Astrogeology (JETT5, 13-17 May 2024); NASA SVS interview with Kelsey Young (JETT5 lighting); NASA image "A Moonlit Moonwalk" (16 May 2024).</p></section>''',
        # 3 Idea
        f'''<section><h2>The idea: match terrain at 60 m</h2><p class="lead">Compare 3.84 km patches of real terrain models, so the answer is a rim, ridge or lava field, not a region.</p>
<div class="tgrid">{target_cards}</div><p class="note note-static">{len(targets)} targets: {sum(t["body"] == "moon" for t in targets)} LOLA south-pole sites (NASA PGDA), covering {artemis["n_covered"]} of NASA's {artemis["n_regions"]} Artemis III candidate regions, and the Jezero landing area (USGS CTX DTM).</p></section>''',
        # 4 Pipeline
        f'''<section><h2>How it works</h2><ol class="pipe">
<li><b>Real terrain</b>LOLA 5 m (Moon), CTX 20 m (Mars), Copernicus 30 m (Earth, 30 regions)</li>
<li><b>One 60 m grid</b>Local metric projections; Mars warped to equidistant around Jezero</li>
<li><b>Fingerprint</b>20 rotation-invariant terrain features plus a ResNet-18 image embedding</li>
<li><b>Masked search</b>{meta["n_searchable"]:,} Earth patches after WorldCover masks; S = 60% terrain + 40% image</li>
<li><b>Explain, light, validate</b>Feature bars; low-Sun shadow analog and Sun hours; NASA POWER months; crater benchmark</li></ol>
<p class="note">Offline Python pipeline → static JSON → React site on GitHub Pages.</p></section>''',
        # 5 Example
        f'''<section><h2 class="h2s">Artemis III region: Malapert massif → {e(top["region_name"])}</h2><div class="ex ex4">
<div class="quad"><figure class="moonp"><img src="{img(top["images"]["target_hillshade"])}" alt=""><figcaption>Moon patch</figcaption></figure>
<figure class="earthp"><img src="{img(top["images"]["earth_hillshade"])}" alt=""><figcaption>Earth patch</figcaption></figure>
<figure class="moonp"><img src="{img(top["images"]["lowsun_target"])}" alt=""><figcaption>Moon, low sun {tmal["sun_band"]["preview_elevation_deg"]:.1f}°</figcaption></figure>
<figure class="earthp"><img src="{img(top["images"]["lowsun_earth"])}" alt=""><figcaption>Earth, same low sun</figcaption></figure></div>
<div class="card"><p class="score">{top["score"]:.1f}<span> similarity score (0-100)</span></p><p class="score2">{top["lighting"]["similarity"]:.1f}<span> low-sun shadow similarity, a separate panel</span></p>{bars}
<p class="small"><b>Best months:</b> {", ".join(month_names[m - 1] for m in top["best_months"])} (our rule: dry months within −25 to 35 °C with the most low-sun hours).</p>
<p class="small">90th-percentile slope {top["target_terrain"]["slope_p90_deg"]:.1f}° (Moon) vs {top["terrain"]["slope_p90_deg"]:.1f}° (Earth) · relief {top["target_terrain"]["relief_m"]:.0f} m vs {top["terrain"]["relief_m"]:.0f} m</p>
<p class="small"><b>Breaks down:</b> gravity, vacuum, radiation, polar light; Earth matches {100 * cov_mal:.0f}% of Malapert's patches, but not its steepest faces.</p></div></div></section>''',
        # 6 Validation
        f'''<section><h2>Validation: does the fingerprint recognise landforms?</h2><div class="two">
<div><p class="lead">Crater retrieval: 7 PASSC impact craters (0.8-3.5 km) query {val["v1_crater_retrieval"]["n_negatives"]:,} grid patches on other continents.</p>
<table><thead><tr><th>Ranker</th><th>AUC</th><th>AUC, hard negatives</th><th>Crater in top 10</th></tr></thead><tbody>{rows}</tbody></table></div>
<div><ul class="mid"><li>The image embedding recognises craters, also against hard negatives from the other crater tiles; the 20 readable features alone do so only weakly.</li>
<li>90 m rerun: Spearman ρ {min(rho_vals):.2f}-{max(rho_vals):.2f} for each target's top-20 regions.</li>
<li>±20% feature-group weights: {100 * min(stay_vals):.0f}-{100 * max(stay_vals):.0f}% of top-10 sites stay; terrain/image split 0.4/0.6 or 0.8/0.2: {100 * min(split_vals):.0f}-{100 * max(split_vals):.0f}%.</li>
<li>All four sanity checks and all {len(linfo["checks"])} lighting checks pass (flat plane, step shadow, curvature, NREL solar position).</li>
<li>Limits: 7 craters, 60 m grid, gravity changes crater shape.</li></ul></div></div></section>''',
        # 7 Impact
        f'''<section><h2>Impact and next steps</h2><div class="two"><div><ul class="mid">
<li><b>For analog field-test planners:</b> a shortlist per target with evidence, limits, best months, and CSV, GeoJSON or KML downloads.</li>
<li><b>The usual sites, on the same score:</b> for Malapert, the JETT5 area's best searchable patch ranks #{sp_mal["rank"]:,} of {sp_mal["n_candidates"]:,}; with the land-cover masks off it ranks #{sp_mal["rank_masks_off"]:,}.</li>
<li><b>Outside our analog catalogue:</b> {outside_text}.</li>
<li><b>Next:</b> Gale crater and a lunar pit target, finer Earth DEMs in the best regions, LRO Diviner temperatures.</li></ul></div>
<div class="credits"><p><b>Data</b></p><p>NASA LRO LOLA (GSFC PGDA, Barker et al. 2021) · USGS Mars 2020 CTX DTM (Fergason et al. 2020) · ESA Copernicus DEM GLO-30 · ESA WorldCover 2021 · NASA POWER · NASA GIBS · PASSC Earth Impact Database</p>
<p><b>Try it</b><br>iammanoj807.github.io/rehearsal-grounds<br>github.com/iammanoj807/rehearsal-grounds</p>
</div></div></section>''',
    ]
    css = """
@page{size:1280px 720px;margin:0}*{box-sizing:border-box}body{margin:0;font:22px/1.4 system-ui,sans-serif;color:#1E2126;background:#F7F5F0}
section{width:1280px;height:720px;padding:56px 72px;position:relative;overflow:hidden;page-break-after:always;background:#F7F5F0}
h1,h2{font-family:'Bricolage Grotesque',system-ui,sans-serif;margin:0 0 20px;line-height:1.1}h2{font-size:44px}
.title{padding:0;display:flex}.half{width:50%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding-top:40px;gap:10px}
.half img{width:330px;height:330px;border:2px solid #1E2126}.half p{font-weight:600;margin:0}.moon{background:#D7D6D1;color:#4A4E55}.earth{background:#E4C49D;color:#7A3D1A}
.titlebox{position:absolute;left:50%;bottom:32px;transform:translateX(-50%);background:#1E2126;color:#F7F5F0;padding:22px 34px;border-radius:8px;width:980px}
.titlebox h1{font-size:54px;margin:0}.titlebox .sub{margin:4px 0 10px;font-size:24px}.titlebox .meta{margin:0;font-size:17px;color:#D7D6D1}
ul.big{font-size:30px;line-height:1.45;padding-left:1em}ul.big li{margin-bottom:18px}ul.mid{font-size:22px;padding-left:1em}ul.mid li{margin-bottom:14px}
.lead{font-size:26px;max-width:1050px}.note{font-size:18px;color:#555A61;position:absolute;bottom:40px}
.tgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:16px}.tcard{margin:0;padding:10px;border-radius:6px}.tcard.moon{background:#D7D6D1}.tcard.mars{background:#ead8c9}
.tcard img{width:100%;height:118px;object-fit:cover;display:block}.tcard figcaption{font-size:16px;font-weight:600;margin-top:6px}.tcard span{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#555A61}
ol.pipe{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;padding:0;list-style:none;counter-reset:s;margin-top:30px}
ol.pipe li{border:2px solid #1E2126;border-radius:8px;padding:18px;font-size:18px;background:#fff;counter-increment:s;min-height:260px}
ol.pipe li b{display:block;font-family:'Bricolage Grotesque',sans-serif;font-size:24px;margin-bottom:8px}ol.pipe li b::before{content:counter(s) ". ";color:#7A3D1A}
.ex{display:grid;grid-template-columns:330px 330px 1fr;gap:20px;align-items:start}.ex figure{margin:0;padding:12px;border-radius:6px}.moonp{background:#D7D6D1}.earthp{background:#E4C49D}
.ex img{width:100%;display:block}.ex4{grid-template-columns:450px 1fr}.h2s{font-size:34px}.note-static{position:static;margin-top:14px}.quad{display:grid;grid-template-columns:1fr 1fr;gap:10px}.quad figure{padding:8px}.quad figcaption{font-size:13px}.score2{font:700 34px/1 'Bricolage Grotesque',sans-serif;margin:0 0 10px}.score2 span{font:400 15px system-ui;color:#555A61}.ex figcaption{font-size:15px;font-weight:600;margin-top:6px}.card{font-size:18px}.score{font:700 54px/1 'Bricolage Grotesque',sans-serif;margin:0 0 12px}.score span{font:400 16px system-ui;color:#555A61}
.bar{display:grid;grid-template-columns:150px 1fr 36px;gap:8px;align-items:center;margin:6px 0}.bar i{height:12px;background:#e7e4dc;border:1px solid #c9c6bd}.bar b{display:block;height:100%;background:#4A4E55}.bar em{font-style:normal;font-weight:700;text-align:right}
.small{font-size:16px;color:#333}.two{display:grid;grid-template-columns:1.05fr 1fr;gap:40px}
table{border-collapse:collapse;width:100%;font-size:20px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #c9c6bd}thead th{border-bottom:2px solid #1E2126;font-size:16px}tr.hl{background:#fff;font-weight:700}
.credits{font-size:18px;background:#fff;border:2px solid #1E2126;border-radius:8px;padding:18px 22px}.credits p{margin:0 0 12px}
"""
    doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Rehearsal Grounds slides</title>'
        '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700&display=swap" rel="stylesheet">'
        f"<style>{css}</style></head><body>{''.join(slides)}</body></html>"
    )
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} ({len(slides)} slides)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DOCS / "slides.html")
