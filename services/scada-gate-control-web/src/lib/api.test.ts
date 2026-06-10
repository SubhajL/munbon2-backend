import { describe, expect, test, vi } from 'vitest';
import { ApiError, createApiClient, type SiteSummary } from './api';

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('createApiClient.listSites', () => {
  test('GETs /api/sites with the bearer token and parses the body', async () => {
    const sites: SiteSummary[] = [
      { id: 'waste-way', name: 'Waste Way', connection: 'ok', markerColor: 'green', lastUpdated: null },
    ];
    const fetchImpl = vi.fn(async () => jsonResponse(sites));
    const client = createApiClient({ baseUrl: 'http://api', token: 'tok', fetchImpl });

    expect(await client.listSites()).toEqual(sites);
    expect(fetchImpl).toHaveBeenCalledWith('http://api/api/sites', {
      headers: { authorization: 'Bearer tok' },
    });
  });

  test('throws ApiError carrying the HTTP status on failure', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ error: 'unauthorized' }, 401));
    const client = createApiClient({ baseUrl: 'http://api', fetchImpl });
    await expect(client.listSites()).rejects.toMatchObject({ status: 401 });
    await expect(client.listSites()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('createApiClient.commandLevel', () => {
  test('POSTs the command and returns the structured result (202 accepted)', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ status: 'accepted', pending: true }, 202));
    const client = createApiClient({ baseUrl: 'http://api', token: 't', fetchImpl });

    expect(await client.commandLevel('waste-way', 2, true)).toEqual({
      status: 'accepted',
      pending: true,
    });
    expect(fetchImpl).toHaveBeenCalledWith('http://api/api/gates/waste-way/command-level', {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: 'Bearer t' },
      body: JSON.stringify({ targetValue: 2, confirmed: true }),
    });
  });

  test('returns the rejection body for a 4xx with a structured result', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ status: 'rejected', reason: 'data_offline' }, 409));
    const client = createApiClient({ baseUrl: 'http://api', fetchImpl });
    expect(await client.commandLevel('waste-way', 2, true)).toEqual({
      status: 'rejected',
      reason: 'data_offline',
    });
  });
});
