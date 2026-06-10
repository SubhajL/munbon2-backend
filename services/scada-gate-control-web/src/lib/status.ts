/**
 * Pure UI status helpers — connection summary counts, status colour tokens, and
 * Thai/English status labels. No React, fully unit-testable.
 */
import type { MarkerColor, Quality, SiteSummary } from './api';

export type ConnectionSummary = { online: number; stale: number; offline: number };

export function summarizeConnections(sites: readonly SiteSummary[]): ConnectionSummary {
  return sites.reduce<ConnectionSummary>(
    (acc, site) => {
      if (site.markerColor === 'green') return { ...acc, online: acc.online + 1 };
      if (site.markerColor === 'yellow') return { ...acc, stale: acc.stale + 1 };
      return { ...acc, offline: acc.offline + 1 };
    },
    { online: 0, stale: 0, offline: 0 },
  );
}

/** CSS custom-property reference for a marker colour (design-token driven). */
export const STATUS_COLOR_VAR: Record<MarkerColor, string> = {
  green: 'var(--color-online)',
  yellow: 'var(--color-stale)',
  red: 'var(--color-offline)',
};

/** Bilingual label for a connection quality (Thai + English). */
export function connectionLabel(quality: Quality): { th: string; en: string } {
  switch (quality) {
    case 'ok':
      return { th: 'ออนไลน์', en: 'Online' };
    case 'stale':
      return { th: 'ข้อมูลเก่า', en: 'Stale' };
    case 'offline':
      return { th: 'ออฟไลน์', en: 'Offline' };
    case 'modbus_exception':
      return { th: 'ข้อผิดพลาด Modbus', en: 'Modbus error' };
    case 'decode_error':
      return { th: 'ถอดรหัสค่าไม่ได้', en: 'Decode error' };
  }
}
