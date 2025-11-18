export type RequestGate = {
  start: (input: any, init?: any) => Promise<{ reqId: number; response: any }>;
  isCurrent: (reqId: number) => boolean;
};

/**
 * Creates a gate around fetch that ensures only the latest request is considered current.
 * - Aborts the previous inflight request when start(...) is called again
 * - Returns a tagged response { reqId, response }
 * - Call isCurrent(reqId) to ignore stale responses
 */
export function createRequestGate(fetchImpl: any = (globalThis as any).fetch): RequestGate {
  let lastReqId = 0;
  let controller: AbortController | null = null;

  function isCurrent(reqId: number) {
    return reqId === lastReqId;
  }

  async function start(input: any, init?: any) {
    // Abort old
    if (controller) controller.abort();
    controller = new AbortController();
    const reqId = ++lastReqId;

    try {
      const response = await fetchImpl(input, { ...(init || {}), signal: controller.signal });
      return { reqId, response };
    } catch (e: any) {
      // If aborted, rethrow to let caller handle gracefully
      throw e;
    }
  }

  return { start, isCurrent };
}

export function isAbortError(e: unknown): boolean {
  return (
    !!e &&
    typeof e === 'object' &&
    (e as any).name === 'AbortError'
  );
}