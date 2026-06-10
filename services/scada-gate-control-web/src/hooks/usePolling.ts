"use client";

import { useEffect, useRef, useState } from "react";

export type PollState<T> = {
  readonly data: T | null;
  readonly error: Error | null;
  readonly loading: boolean;
};

/**
 * Polls `fetcher` immediately then every `intervalMs`. Keeps the last good data
 * when a fetch fails (stale-while-error) so the UI can show a "stale" state
 * rather than blanking. Pass `enabled: false` to pause polling.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
): PollState<T> {
  const [state, setState] = useState<PollState<T>>({
    data: null,
    error: null,
    loading: enabled,
  });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const tick = async (): Promise<void> => {
      try {
        const data = await fetcherRef.current();
        if (active) setState({ data, error: null, loading: false });
      } catch (error) {
        if (active) {
          setState((prev) => ({
            data: prev.data,
            error: error as Error,
            loading: false,
          }));
        }
      }
    };
    void tick();
    const id = setInterval(() => void tick(), intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [intervalMs, enabled]);

  return state;
}
