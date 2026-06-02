"""Fusion: combine EXIF, vision signals, OCR and geocoding into one ranked result.

Decision order for the *location* (most reliable first):
  1. EXIF GPS            -> exact, location_source="exif"
  2. OCR -> geocoded     -> real place from a readable sign, location_source="ocr"
  3. GeoCLIP             -> predicted GPS coordinates (GeoSpy-style),
                            reverse-geocoded to place names, location_source="geoclip"
  4. CLIP/StreetCLIP     -> country/region inference, location_source="inference"

City / district from (3) and (4) are model estimates and are labelled as such in
the hierarchy note. (1)/(2) provide exact/real places. GeoCLIP is optional: if its
weights cannot load, the pipeline degrades to (4) automatically.
"""
from __future__ import annotations

import asyncio
from math import asin, cos, radians, sin, sqrt

from PIL import Image

from ..config import get_settings
from ..schemas import (AnalysisResult, GpsInfo, Hierarchy, LocationCandidate,
                       ReferenceMatch, SignalGroup, SignalScore)
from . import geocode, ocr, reference
from .exif import extract_gps, open_image
from .geoengine import get_geo_engine
from .labels import (COUNTRY_PROMPT, COUNTRY_NAMES, COUNTRY_TO_CONTINENT,
                     REGION_PROMPT, REGIONS, SIGNAL_GROUPS)
from .vision import get_engine


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _cluster_coords(preds: list[tuple[float, float, float]],
                    radius_km: float) -> list[tuple[float, float, float]]:
    """Greedy confidence-weighted clustering of (lat, lon, prob) predictions.

    Predictions within `radius_km` of a cluster's running centroid are merged;
    each cluster's probability is the sum of its members and its position is the
    probability-weighted centroid. Returns [(lat, lon, prob), ...] by prob desc.
    This turns many noisy point guesses (incl. TTA views) into a few robust ones.
    """
    clusters: list[dict] = []
    for lat, lon, p in sorted(preds, key=lambda x: x[2], reverse=True):
        for c in clusters:
            if _haversine_km((lat, lon), (c["lat"], c["lon"])) <= radius_km:
                c["pts"].append((lat, lon, p))
                tot = sum(pp for _, _, pp in c["pts"])
                c["lat"] = sum(la * pp for la, _, pp in c["pts"]) / tot
                c["lon"] = sum(lo * pp for _, lo, pp in c["pts"]) / tot
                c["prob"] = tot
                break
        else:
            clusters.append({"lat": lat, "lon": lon, "prob": p, "pts": [(lat, lon, p)]})
    clusters.sort(key=lambda c: c["prob"], reverse=True)
    return [(c["lat"], c["lon"], c["prob"]) for c in clusters]


def _short_label(addr: dict, display: str) -> str:
    """Compact human label from a reverse-geocoded address."""
    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("municipality") or addr.get("county"))
    region = addr.get("state") or addr.get("region")
    country = addr.get("country")
    parts = [p for p in (city, region, country) if p]
    return ", ".join(parts) if parts else (display or "")


def _analyze_signals(image: Image.Image) -> tuple[list[SignalGroup], dict]:
    """Run each visual-analysis group; weight = top score, normalized across groups."""
    engine = get_engine()
    groups: list[SignalGroup] = []
    tops: dict[str, tuple[str, float]] = {}
    raw_weights: dict[str, float] = {}
    for group_name, mapping in SIGNAL_GROUPS.items():
        labels = list(mapping.keys())
        prompts = list(mapping.values())
        # zero_shot uses a template; here prompts are full sentences already
        ranked = engine.zero_shot(image, prompts, template="{}", top_k=3)
        prompt_to_label = {v: k for k, v in mapping.items()}
        top = [SignalScore(label=prompt_to_label.get(p, p), score=round(s, 4)) for p, s in ranked]
        groups.append(SignalGroup(name=group_name, top=top, weight=0.0))
        if top:
            tops[group_name] = (top[0].label, top[0].score)
            raw_weights[group_name] = top[0].score
    total = sum(raw_weights.values()) or 1.0
    for g in groups:
        g.weight = round(raw_weights.get(g.name, 0.0) / total, 3)
    return groups, tops


def _reasoning_from_signals(tops: dict, country: str) -> str:
    bits = []
    if "Landschaft" in tops:
        bits.append(f"Landschaft ähnelt „{tops['Landschaft'][0]}“")
    if "Architektur" in tops:
        bits.append(f"Architektur weist auf „{tops['Architektur'][0]}“")
    if "Infrastruktur" in tops:
        bits.append(f"Infrastruktur passt zu „{tops['Infrastruktur'][0]}“")
    if "Klima" in tops:
        bits.append(f"Klima-Hinweise: „{tops['Klima'][0]}“")
    joined = "; ".join(bits)
    return f"{joined} → konsistent mit {country}." if joined else f"Modellähnlichkeit zu {country}."


async def analyze_image(data: bytes, source_name: str = "") -> AnalysisResult:
    image = open_image(data)
    engine = get_engine()
    geo = get_geo_engine()

    # --- visual signals + coordinate prediction (CPU/GPU bound -> thread) ---
    def _vision():
        groups, tops = _analyze_signals(image)
        countries = engine.zero_shot(image, COUNTRY_NAMES, template=COUNTRY_PROMPT, top_k=10)
        region = None
        if countries:
            regs = REGIONS.get(countries[0][0])
            if regs:
                ranked = engine.zero_shot(image, regs, template=REGION_PROMPT, top_k=1)
                if ranked:
                    # strip the appended ", Country" for display
                    region = ranked[0][0].split(",")[0]
        img_vec = engine.embed_image(image)
        geo_preds = geo.predict(image)  # [(lat, lon, prob), ...] or [] if unavailable
        return groups, tops, countries, region, img_vec, geo_preds

    groups, tops, countries, inferred_region, img_vec, geo_preds = await asyncio.to_thread(_vision)

    # --- EXIF GPS ---
    gps_raw = extract_gps(data)
    gps = GpsInfo(**{k: gps_raw.get(k) for k in
                     ("has_gps", "lat", "lon", "altitude", "timestamp", "camera")})

    # --- OCR (optional) ---
    ocr_text = ""
    ocr_places: list[dict] = []
    if ocr.available():
        ocr_text = await asyncio.to_thread(ocr.read_text, image)
        for q in ocr.candidate_queries(ocr_text):
            hits = await geocode.forward(q, limit=2)
            ocr_places.extend(hits)
        # de-dup by rounded coords, keep most important
        seen = set()
        uniq = []
        for p in sorted(ocr_places, key=lambda x: x["importance"], reverse=True):
            key = (round(p["lat"], 3), round(p["lon"], 3))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(p)
        ocr_places = uniq[:5]

    # --- reference similarity (optional) ---
    ref_matches = [ReferenceMatch(**m) for m in reference.match(img_vec, top_k=5)]

    # --- decide location source + hierarchy + candidates ---
    hierarchy = Hierarchy()
    candidates: list[LocationCandidate] = []
    location_source = "inference"
    uncertainty = ""

    if gps.has_gps:
        location_source = "exif"
        rev = await geocode.reverse(gps.lat, gps.lon)
        addr = (rev or {}).get("address", {})
        gps.address = (rev or {}).get("display", "")
        hierarchy = Hierarchy(
            continent=None,
            country=addr.get("country"),
            region=addr.get("state") or addr.get("region"),
            city=addr.get("city") or addr.get("town") or addr.get("village"),
            district=addr.get("suburb") or addr.get("city_district"),
            note="Exakt aus GPS-Metadaten.",
        )
        candidates.append(LocationCandidate(
            rank=1, label=gps.address or f"{gps.lat:.5f}, {gps.lon:.5f}",
            confidence=0.99, lat=gps.lat, lon=gps.lon,
            reasoning="Exakte GPS-Koordinaten aus den EXIF-Metadaten des Fotos.",
        ))
        uncertainty = "Sehr gering — Standort stammt direkt aus GPS-Metadaten."

    elif ocr_places:
        location_source = "ocr"
        top = ocr_places[0]
        rev = await geocode.reverse(top["lat"], top["lon"])
        addr = (rev or {}).get("address", {})
        hierarchy = Hierarchy(
            country=addr.get("country"),
            region=addr.get("state") or addr.get("region"),
            city=addr.get("city") or addr.get("town") or addr.get("village"),
            district=addr.get("suburb") or addr.get("city_district"),
            note="Aus lesbarem Text im Bild (Schild) abgeleitet und geocodiert.",
        )
        for i, p in enumerate(ocr_places, start=1):
            short = ", ".join(p["display"].split(",")[:2])
            candidates.append(LocationCandidate(
                rank=i, label=short or p["display"],
                confidence=round(min(0.9, 0.4 + p["importance"]), 3),
                lat=p["lat"], lon=p["lon"],
                reasoning="Aus erkanntem Schild-/Ortstext per Geocoding gefunden.",
            ))
        uncertainty = "Mittel — abhängig davon, ob der erkannte Text wirklich der Aufnahmeort ist."

    elif geo_preds:
        # --- GeoCLIP: real coordinate prediction (GeoSpy-style) -------------
        # Pool TTA + top-k point guesses into a few robust clusters.
        location_source = "geoclip"
        clustered = _cluster_coords(geo_preds, get_settings().geoclip_cluster_km)[:10]
        revs = []
        for lat, lon, _ in clustered[:5]:           # reverse-geocode only the best few
            rev = await geocode.reverse(lat, lon)
            revs.append(rev or {})
        while len(revs) < len(clustered):
            revs.append({})
        top_addr = revs[0].get("address", {})
        sc = countries[0][0] if countries else None
        hierarchy = Hierarchy(
            continent=COUNTRY_TO_CONTINENT.get(top_addr.get("country")) if top_addr.get("country") else None,
            country=top_addr.get("country"),
            region=top_addr.get("state") or top_addr.get("region"),
            city=top_addr.get("city") or top_addr.get("town") or top_addr.get("village")
                 or top_addr.get("municipality"),
            district=top_addr.get("suburb") or top_addr.get("city_district"),
            note="Aus GeoCLIP-Koordinatenvorhersage rückwärts-geocodiert. Dies ist eine "
                 "Modell-Schätzung der Koordinaten (kein GPS); die Stadt-/Stadtteil-Ebene "
                 "kann ungenau sein."
                 + (f" StreetCLIP-Kontext stützt: {sc}." if sc else ""),
        )
        total = sum(p for _, _, p in clustered) or 1.0
        for i, ((lat, lon, p), rev) in enumerate(zip(clustered, revs), start=1):
            addr = rev.get("address", {})
            label = _short_label(addr, rev.get("display", "")) or f"{lat:.4f}, {lon:.4f}"
            candidates.append(LocationCandidate(
                rank=i, label=label, confidence=round(p / total, 3),
                lat=lat, lon=lon,
                reasoning="GeoCLIP-Koordinatenvorhersage (TTA + Clustering). "
                          + _reasoning_from_signals(tops, hierarchy.country or "dem Land"),
            ))
        spread = (_haversine_km((clustered[0][0], clustered[0][1]),
                                (clustered[1][0], clustered[1][1]))
                  if len(clustered) > 1 else 0.0)
        uncertainty = (
            f"GeoCLIP-Koordinaten. Streuung Top-1↔Top-2: ~{spread:.0f} km. "
            + ("Vorhersagen liegen nah beieinander → höhere Zuversicht. " if spread < 25
               else "Vorhersagen streuen → geringere Zuversicht. ")
            + (f"StreetCLIP-Kontext nennt {sc}. " if sc else "")
            + "Koordinaten sind eine Modell-Schätzung, kein GPS."
        )

    else:
        location_source = "inference"
        top_country = countries[0][0] if countries else None
        region_note = " Region ist eine grobe Inferenz." if inferred_region else ""
        hierarchy = Hierarchy(
            continent=COUNTRY_TO_CONTINENT.get(top_country) if top_country else None,
            country=top_country,
            region=inferred_region, city=None, district=None,
            note="Stadt/Stadtteil sind aus dem Bildinhalt nicht zuverlässig bestimmbar "
                 "(kein GPS, kein lesbares Ortsschild). Es wird ehrlich nur Land/Region geschätzt."
                 + region_note,
        )
        # Geocode centroids of the top countries for map markers (limit network calls)
        coords: dict[str, tuple[float, float]] = {}
        for name, _ in countries[:5]:
            hits = await geocode.forward(name, limit=1)
            if hits:
                coords[name] = (hits[0]["lat"], hits[0]["lon"])
        for i, (name, score) in enumerate(countries, start=1):
            latlon = coords.get(name)
            candidates.append(LocationCandidate(
                rank=i, label=name, confidence=round(score, 3),
                lat=latlon[0] if latlon else None,
                lon=latlon[1] if latlon else None,
                reasoning=_reasoning_from_signals(tops, name),
            ))
        spread = countries[0][1] - countries[1][1] if len(countries) > 1 else 0.0
        uncertainty = ("Hoch — reine Bildinferenz auf Land-/Regionsebene. "
                       f"Abstand Top-1 zu Top-2: {spread:.2f}. Kein Stadt-/Adress-Treffer.")

    return AnalysisResult(
        kind="image", source_name=source_name,
        gps=gps, location_source=location_source, hierarchy=hierarchy,
        candidates=candidates[:10], signals=groups, ocr_text=ocr_text,
        reference_matches=ref_matches, uncertainty=uncertainty,
        model_used=engine.model_name or "(lazy)",
    )


async def analyze_video(data: bytes, source_name: str = "") -> AnalysisResult:
    """Sample keyframes, analyse each, aggregate country votes."""
    from .video import extract_keyframes

    frames = await asyncio.to_thread(extract_keyframes, data)
    if not frames:
        res = AnalysisResult(kind="video", source_name=source_name,
                             uncertainty="Keine Frames extrahierbar.")
        return res

    engine = get_engine()
    geo = get_geo_engine()

    def _analyze():
        agg: dict[str, float] = {}
        pts: list[tuple[float, float, float]] = []
        for fr in frames:
            for name, score in engine.zero_shot(fr, COUNTRY_NAMES, template=COUNTRY_PROMPT, top_k=5):
                agg[name] = agg.get(name, 0.0) + score
            preds = geo.predict(fr, top_k=1, tta=False)  # speed: 1 view per frame
            if preds:
                pts.append(preds[0])
        return agg, pts

    agg, pts = await asyncio.to_thread(_analyze)

    # --- GeoCLIP path: aggregate frame coordinates by their medoid ----------
    if pts:
        def _cost(i: int) -> float:
            return sum(_haversine_km((pts[i][0], pts[i][1]), (q[0], q[1])) for q in pts)

        medoid = min(range(len(pts)), key=_cost)
        mlat, mlon, _ = pts[medoid]
        spread = sum(_haversine_km((mlat, mlon), (q[0], q[1])) for q in pts) / len(pts)
        rev = await geocode.reverse(mlat, mlon)
        addr = (rev or {}).get("address", {})

        uniq: dict[tuple[float, float], tuple[float, float, float]] = {}
        for lat, lon, p in pts:
            key = (round(lat, 2), round(lon, 2))
            if key not in uniq or p > uniq[key][2]:
                uniq[key] = (lat, lon, p)
        ordered = sorted(uniq.values(),
                         key=lambda q: _haversine_km((mlat, mlon), (q[0], q[1])))[:10]
        candidates = []
        for i, (lat, lon, p) in enumerate(ordered, start=1):
            label = f"{lat:.4f}, {lon:.4f}"
            if i <= 5:  # limit reverse-geocoding network calls
                r = await geocode.reverse(lat, lon)
                label = _short_label((r or {}).get("address", {}),
                                     (r or {}).get("display", "")) or label
            candidates.append(LocationCandidate(
                rank=i, label=label, confidence=round(p, 3), lat=lat, lon=lon,
                reasoning=f"GeoCLIP-Vorhersage aus Videoframe "
                          f"(~{_haversine_km((mlat, mlon), (lat, lon)):.0f} km vom Zentrum).",
            ))
        return AnalysisResult(
            kind="video", source_name=source_name, location_source="geoclip",
            hierarchy=Hierarchy(
                continent=COUNTRY_TO_CONTINENT.get(addr.get("country")) if addr.get("country") else None,
                country=addr.get("country"),
                region=addr.get("state") or addr.get("region"),
                city=addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality"),
                district=addr.get("suburb") or addr.get("city_district"),
                note=f"GeoCLIP-Koordinaten über {len(frames)} Frames; zentralster Punkt (Medoid) "
                     f"rückwärts-geocodiert. Mittlere Streuung ~{spread:.0f} km. Modell-Schätzung, kein GPS.",
            ),
            candidates=candidates,
            uncertainty=(f"Mittel — GeoCLIP-Koordinaten über {len(frames)} Frames, "
                         f"mittlere Streuung zum Zentrum ~{spread:.0f} km. Kein GPS."),
            model_used=engine.model_name or "(lazy)",
        )

    # --- fallback: StreetCLIP country vote ----------------------------------
    total = sum(agg.values()) or 1.0
    ranked = sorted(((k, v / total) for k, v in agg.items()), key=lambda x: x[1], reverse=True)[:10]

    coords: dict[str, tuple[float, float]] = {}
    for name, _ in ranked[:5]:
        hits = await geocode.forward(name, limit=1)
        if hits:
            coords[name] = (hits[0]["lat"], hits[0]["lon"])

    candidates = [
        LocationCandidate(
            rank=i, label=name, confidence=round(score, 3),
            lat=coords.get(name, (None, None))[0], lon=coords.get(name, (None, None))[1],
            reasoning=f"Konsens aus {len(frames)} analysierten Videoframes.",
        )
        for i, (name, score) in enumerate(ranked, start=1)
    ]
    top_country = ranked[0][0] if ranked else None
    return AnalysisResult(
        kind="video", source_name=source_name,
        hierarchy=Hierarchy(continent=COUNTRY_TO_CONTINENT.get(top_country) if top_country else None,
                            country=top_country,
                            note=f"Aggregiert aus {len(frames)} Frames. Route wird bewusst nicht "
                                 "rekonstruiert (aus Bildinhalt nicht zuverlässig möglich)."),
        candidates=candidates, location_source="inference",
        uncertainty="Hoch — Videoinferenz auf Land-/Regionsebene, Konsens über Frames.",
        model_used=engine.model_name or "(lazy)",
    )
