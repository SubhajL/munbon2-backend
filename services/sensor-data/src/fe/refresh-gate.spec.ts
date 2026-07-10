import { createRequestGate, isAbortError } from './refresh-gate';

// Mocks a minimal fetch with abort support
function makeAbortableFetch() {
  const calls: any[] = [];
  const fetchImpl = (input: any, init?: any) => {
    const call: any = { input, init, aborted: false };
    calls.push(call);
    return new Promise<Response>((resolve, reject) => {
      const signal = init?.signal as AbortSignal | undefined;
      if (signal) {
        if (signal.aborted) {
          call.aborted = true;
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        const onAbort = () => {
          call.aborted = true;
          signal.removeEventListener('abort', onAbort);
          reject(new DOMException('Aborted', 'AbortError'));
        };
        signal.addEventListener('abort', onAbort);
      }
      // Resolve on next tick to allow abort to fire first
      setTimeout(() => resolve(new Response('{}', { status: 200 })), 0);
    });
  };
  return { fetchImpl, calls } as const;
}

describe('refresh-gate', () => {
  test('start_aborts_previous_request', async () => {
    const { fetchImpl, calls } = makeAbortableFetch();
    const gate = createRequestGate(fetchImpl as any);

    const p1 = gate.start('url1').catch((e) => e);
    const p2 = gate.start('url2');

    await expect(p2).resolves.toHaveProperty('reqId');
    // First call should be aborted
    const aborted = await p1.catch((e) => e);
    expect(isAbortError(aborted)).toBe(true);
    // wait microtick
    await new Promise((r) => setTimeout(r, 1));
    expect(calls.length).toBe(2);
    expect(calls[0].aborted).toBe(true);
    expect(calls[1].aborted).toBe(false);
  });

  test('ignores_stale_response_when_newer_completed', async () => {
    // Custom fetch that lets us control resolve order
    let resolve1: any, resolve2: any;
    const fetchImpl = (_: any, init?: any) => {
      if ((fetchImpl as any).count === undefined) (fetchImpl as any).count = 0;
      (fetchImpl as any).count++;
      const n = (fetchImpl as any).count;
      return new Promise<Response>((resolve, reject) => {
        const signal = init?.signal as AbortSignal | undefined;
        if (signal) {
          if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'));
          signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        }
        if (n === 1) resolve1 = () => resolve(new Response('old'));
        else resolve2 = () => resolve(new Response('new'));
      });
    };
    const gate = createRequestGate(fetchImpl as any);

    const r1 = gate.start('u1');
    const r2 = gate.start('u2');

    // resolve second (latest) first
    resolve2();
    const res2 = await r2;
    expect(gate.isCurrent(res2.reqId)).toBe(true);

    // resolve first (stale) later
    resolve1();
    const res1 = await r1.catch((e) => e);
    // Even if the promise resolves, consumers should check isCurrent(reqId)
    expect(gate.isCurrent(res2.reqId)).toBe(true);
    expect(gate.isCurrent(res1.reqId)).toBe(false);
  });

  test('bubbles_non_abort_errors', async () => {
    const fetchImpl = () => Promise.reject(new Error('boom'));
    const gate = createRequestGate(fetchImpl as any);

    await expect(gate.start('u')).rejects.toThrow('boom');
    expect(isAbortError(new DOMException('Aborted', 'AbortError'))).toBe(true);
    expect(isAbortError(new Error('x'))).toBe(false);
  });
});