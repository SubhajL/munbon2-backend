"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { ReactNode } from "react";
import Map, { Marker, Popup } from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import type { SiteSummary } from "@/lib/api";
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, GATE_COORDS } from "@/lib/gates";
import { STATUS_COLOR_VAR } from "@/lib/status";

// Open-source raster basemap — no Mapbox token required.
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export type MapViewProps = {
  sites: SiteSummary[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  renderPopup: (site: SiteSummary) => ReactNode;
};

export function MapView({
  sites,
  selectedId,
  onSelect,
  renderPopup,
}: MapViewProps) {
  const selected = sites.find((site) => site.id === selectedId) ?? null;
  const selectedCoords = selected ? GATE_COORDS[selected.id] : undefined;

  return (
    <Map
      initialViewState={{
        longitude: DEFAULT_MAP_CENTER.lng,
        latitude: DEFAULT_MAP_CENTER.lat,
        zoom: DEFAULT_MAP_ZOOM,
      }}
      mapStyle={MAP_STYLE}
      style={{ position: "absolute", inset: 0 }}
    >
      {sites.map((site) => {
        const coords = GATE_COORDS[site.id];
        if (!coords) return null;
        const color = STATUS_COLOR_VAR[site.markerColor];
        return (
          <Marker
            key={site.id}
            longitude={coords.lng}
            latitude={coords.lat}
            onClick={(event) => {
              event.originalEvent.stopPropagation();
              onSelect(site.id);
            }}
          >
            <button
              type="button"
              aria-label={`${site.name} (${site.markerColor})`}
              className="size-4 cursor-pointer rounded-full border-2 border-white/80"
              style={{
                background: color,
                boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 25%, transparent)`,
              }}
            />
          </Marker>
        );
      })}

      {selected && selectedCoords ? (
        <Popup
          longitude={selectedCoords.lng}
          latitude={selectedCoords.lat}
          anchor="bottom"
          offset={16}
          closeOnClick={false}
          onClose={() => onSelect(null)}
          maxWidth="320px"
        >
          {renderPopup(selected)}
        </Popup>
      ) : null}
    </Map>
  );
}
