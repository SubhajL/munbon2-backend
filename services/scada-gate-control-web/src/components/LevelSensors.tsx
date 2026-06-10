'use client';

import { Check } from 'lucide-react';
import type { GateLevel } from '@/lib/api';
import { LEVELS, LEVEL_VALUES } from '@/lib/control';
import { cn } from '@/lib/utils';

export type LevelSensorsProps = {
  currentLevel: GateLevel | null;
  canCommand: boolean;
  onCommand: (level: GateLevel) => void;
  onInfo?: (level: GateLevel) => void;
};

/**
 * The four gate-level sensors. The current level is ON (emerald + check) and
 * non-actionable; OFF levels are command targets. Left-click commands an OFF
 * level (keyboard/touch accessible); right-click mirrors that, and shows the
 * info popup on the ON level (per spec).
 */
export function LevelSensors({ currentLevel, canCommand, onCommand, onInfo }: LevelSensorsProps) {
  const orderedTopDown = [...LEVEL_VALUES].reverse(); // level 4 at top, 1 at bottom

  return (
    <div className="flex flex-col gap-2.5" role="group" aria-label="ระดับประตูน้ำ (Gate levels)">
      {orderedTopDown.map((level) => {
        const meta = LEVELS[level];
        const on = currentLevel === level;
        return (
          <button
            key={level}
            type="button"
            disabled={on || !canCommand}
            aria-pressed={on}
            aria-label={`${meta.thaiLabel} (Level ${level}) — ${on ? 'เปิดอยู่ (on)' : 'ปิดอยู่ (off)'}`}
            onClick={() => {
              if (!on && canCommand) onCommand(level);
            }}
            onContextMenu={(event) => {
              event.preventDefault();
              if (on) onInfo?.(level);
              else if (canCommand) onCommand(level);
            }}
            className={cn(
              'flex items-center gap-3 rounded-xl border p-3 text-left transition-colors',
              on ? 'border-online bg-online/10' : 'border-border hover:bg-surface-high',
              !canCommand && !on && 'cursor-not-allowed opacity-60',
            )}
          >
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-full border-2"
              style={{
                borderColor: on ? 'var(--color-online)' : 'var(--color-border)',
                background: on ? 'var(--color-online)' : 'transparent',
                boxShadow: on
                  ? '0 0 0 4px color-mix(in srgb, var(--color-online) 25%, transparent)'
                  : undefined,
              }}
            >
              {on ? (
                <Check aria-hidden className="size-4" style={{ color: 'var(--color-primary-fg)' }} />
              ) : (
                <span className="text-xs font-semibold tabular-nums text-fg-muted">{level}</span>
              )}
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-medium text-fg">
                {meta.thaiLabel} <span className="text-fg-muted">(Level {level})</span>
              </span>
              <span className="text-xs tabular-nums text-fg-muted">
                {meta.flowRate.toFixed(1)} ลบ.ม./วินาที
              </span>
            </span>
            {on ? (
              <span
                className="ml-auto text-[11px] font-semibold uppercase tracking-wide"
                style={{ color: 'var(--color-online)' }}
              >
                ON
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
