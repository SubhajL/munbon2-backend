/**
 * Fixed gate map placement. Coordinates are PLACEHOLDERS until RID provides the
 * real Waste Way lat/lng and the other Phase-2 gate locations.
 */
export type GateCoords = { readonly lng: number; readonly lat: number };

// Placeholder near the Munbon project area (Nakhon Ratchasima). TODO: real coords.
export const GATE_COORDS: Record<string, GateCoords> = {
  'waste-way': { lng: 101.9, lat: 14.9 },
};

export const DEFAULT_MAP_CENTER: GateCoords = { lng: 101.9, lat: 14.9 };
export const DEFAULT_MAP_ZOOM = 12;
