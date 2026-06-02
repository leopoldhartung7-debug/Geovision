"""Fusion: combine EXIF, vision signals, OCR and geocoding into one ranked result.

Decision order for the *location* (most reliable first):
  1. EXIF GPS            -> exact, location_source="exif"
  2. OCR -> geocoded     -> real place from a readable sign, location_source="ocr"
  3. CLIP/StreetCLIP     -> country/region inference, location_source="inference"

City / district are only filled when (1) or (2) provide them. Otherwise they are
left null with an honest note instead of being guessed.
"""
from __future__ import annotations

import asyncio

from PIL import Image

from ..schemas import (AnalysisResult, GpsInfo, Hierarchy, LocationCandidate,
                       ReferenceMatch, SignalGroup, SignalScore)
from . import geocode, ocr, reference
from .exif import extract_gps, open_image
from .labels import (COUNTRY_PROMPT, COUNTRY_NAMES, COUNTRY_TO_CONTINENT,
                     REGION_PROMPT, REGIONS, SIGNAL_GROUPS)
from .vision import get_engine


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

    # --- visual signals + country inference (CPU/GPU bound -> thread) ---
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
        return groups, tops, countries, region, img_vec

    groups, tops, countries, inferred_region, img_vec = await asyncio.to_thread(_vision)

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

    def _vote():
        agg: dict[str, float] = {}
        for fr in frames:
            for name, score in engine.zero_shot(fr, COUNTRY_NAMES, template=COUNTRY_PROMPT, top_k=5):
                agg[name] = agg.get(name, 0.0) + score
        return agg

    agg = await asyncio.to_thread(_vote)
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
