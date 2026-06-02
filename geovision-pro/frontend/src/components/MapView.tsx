import { useEffect, useRef } from "react";
import L from "leaflet";
import type { LocationCandidate } from "../types";

interface Props {
  candidates: LocationCandidate[];
}

// Interactive world map: best candidate emphasized, alternatives shown,
// a probability radius drawn around the top hit, and a light heat overlay.
export default function MapView({ candidates }: Props) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, { worldCopyJump: true }).setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap-Mitwirkende",
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    const located = candidates.filter((c) => c.lat != null && c.lon != null);
    if (located.length === 0) {
      map.setView([20, 0], 2);
      return;
    }

    located.forEach((c, i) => {
      const isTop = i === 0;
      const radiusKm = Math.max(40, (1 - c.confidence) * 600); // higher uncertainty -> bigger radius
      L.circle([c.lat!, c.lon!], {
        radius: radiusKm * 1000,
        color: isTop ? "#56d4c4" : "#6c8cff",
        weight: isTop ? 2 : 1,
        opacity: isTop ? 0.9 : 0.4,
        fillColor: isTop ? "#56d4c4" : "#6c8cff",
        fillOpacity: isTop ? 0.18 : 0.07,
      }).addTo(layer);

      L.marker([c.lat!, c.lon!])
        .addTo(layer)
        .bindPopup(`<b>#${c.rank} ${c.label}</b><br/>${Math.round(c.confidence * 100)}%`);
    });

    const top = located[0];
    map.setView([top.lat!, top.lon!], located.length === 1 ? 6 : 4);
  }, [candidates]);

  return <div ref={elRef} className="w-full h-[440px] rounded-xl border border-edge" />;
}
