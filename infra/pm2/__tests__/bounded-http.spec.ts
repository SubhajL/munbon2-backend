import { readBoundedResponse } from '../bounded-http';

describe('readBoundedResponse', () => {
  test('returns a response at the exact byte limit', async () => {
    const body = 'a'.repeat(32);
    await expect(readBoundedResponse(new Response(body), 32)).resolves.toBe(body);
  });

  test('cancels collection when a response crosses the byte limit', async () => {
    await expect(readBoundedResponse(new Response('a'.repeat(33)), 32)).rejects.toThrow(
      'probe response is too large',
    );
  });
});
