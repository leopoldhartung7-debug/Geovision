"""Report generation: JSON, CSV and PDF (Executive Summary) from an AnalysisResult."""
from __future__ import annotations

import csv
import io

from ..schemas import AnalysisResult


def to_json_bytes(result: AnalysisResult) -> bytes:
    return result.model_dump_json(indent=2).encode("utf-8")


def to_csv_bytes(result: AnalysisResult) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "label", "confidence", "lat", "lon", "reasoning"])
    for c in result.candidates:
        w.writerow([c.rank, c.label, c.confidence, c.lat or "", c.lon or "", c.reasoning])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def to_pdf_bytes(result: AnalysisResult) -> bytes:
    """Render a clean one/two-page PDF report. Requires reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="GeoVision Pro Report",
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=colors.HexColor("#0b1f3a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#274060"))
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)

    elems = [Paragraph("GeoVision Pro — Standortbericht", h1)]
    elems.append(Paragraph(f"Quelle: {result.source_name or '—'} &nbsp;|&nbsp; "
                           f"Typ: {result.kind} &nbsp;|&nbsp; Modell: {result.model_used}", small))
    elems.append(Spacer(1, 8))

    # Executive summary
    elems.append(Paragraph("Executive Summary", h2))
    best = result.candidates[0] if result.candidates else None
    summary = (f"Wahrscheinlichster Ort: <b>{best.label}</b> "
               f"(Konfidenz {best.confidence:.0%}). " if best else "Kein Standortkandidat. ")
    summary += f"Quelle der Standortbestimmung: <b>{result.location_source}</b>. "
    summary += f"Unsicherheit: {result.uncertainty}"
    elems.append(Paragraph(summary, body))
    elems.append(Spacer(1, 6))

    # Hierarchy
    h = result.hierarchy
    rows = [["Ebene", "Wert"]]
    for lbl, val in [("Kontinent", h.continent), ("Land", h.country),
                     ("Region", h.region), ("Stadt", h.city), ("Stadtteil", h.district)]:
        rows.append([lbl, val or "— (nicht bestimmbar)"])
    t = Table(rows, colWidths=[40 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#274060")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d4e3")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f9")]),
    ]))
    elems.append(Paragraph("Standort-Hierarchie", h2))
    elems.append(t)
    if h.note:
        elems.append(Paragraph(h.note, small))
    elems.append(Spacer(1, 8))

    # Candidates
    elems.append(Paragraph("Standort-Hypothesen (Top 10)", h2))
    crows = [["#", "Ort", "Konfidenz", "Begründung"]]
    for c in result.candidates:
        crows.append([str(c.rank), Paragraph(str(c.label), small),
                      f"{c.confidence:.0%}", Paragraph(c.reasoning, small)])
    ct = Table(crows, colWidths=[8 * mm, 52 * mm, 20 * mm, 80 * mm])
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#274060")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d4e3")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elems.append(ct)
    elems.append(Spacer(1, 8))

    # Signal weights
    if result.signals:
        elems.append(Paragraph("Erklärung — Gewichtung der Bildmerkmale", h2))
        srows = [["Kategorie", "Top-Merkmal", "Gewicht"]]
        for g in result.signals:
            top = g.top[0].label if g.top else "—"
            srows.append([g.name, top, f"{g.weight:.0%}"])
        st = Table(srows, colWidths=[45 * mm, 75 * mm, 25 * mm])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#274060")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d4e3")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elems.append(st)

    elems.append(Spacer(1, 10))
    elems.append(Paragraph(
        "Hinweis: GeoVision Pro liefert exakte Orte nur bei GPS-Metadaten oder lesbaren "
        "Ortsschildern. Reine Bildinferenz erreicht Land-/Regionsebene, nicht Hausnummern.",
        small))

    doc.build(elems)
    return buf.getvalue()
