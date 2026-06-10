/**
 * Typed client for the scada-gate-control backend. Mirrors the API contract in
 * services/scada-gate-control. `fetchImpl` is injectable for testing.
 */
export type Quality = 'ok' | 'stale' | 'offline' | 'modbus_exception' | 'decode_error';
export type MarkerColor = 'green' | 'yellow' | 'red';
export type GateLevel = 1 | 2 | 3 | 4;

export type SiteSummary = {
  id: string;
  name: string;
  connection: Quality;
  markerColor: MarkerColor;
  lastUpdated: string | null;
};

export type GateLevelValue = {
  level: GateLevel;
  thaiLabel: string;
  technicalLabel: string;
  flowRate: number;
};

export type PointSnapshot<T> = {
  raw: number | null;
  value: T | null;
  quality: Quality;
  lastUpdated: string | null;
  lastError: string | null;
};

export type GateStatus = {
  id: string;
  name: string;
  endpoint: { host: string; port: number; unitId: number };
  connection: Quality;
  markerColor: MarkerColor;
  lastUpdated: string | null;
  lastError: string | null;
  gateLevel: PointSnapshot<GateLevelValue>;
  doorSw: PointSnapshot<{ closed: boolean; thaiLabel: string }>;
  horn: PointSnapshot<{ on: boolean; thaiLabel: string }>;
  gateCf: PointSnapshot<{ confirmed: boolean }>;
};

export type CommandResult =
  | { status: 'accepted'; pending: boolean }
  | { status: 'rejected'; reason: string }
  | { status: 'error'; error: string };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type ApiClientOptions = {
  baseUrl: string;
  token?: string;
  fetchImpl?: typeof fetch;
};

export type ApiClient = {
  listSites(): Promise<SiteSummary[]>;
  getGateStatus(id: string): Promise<GateStatus>;
  commandLevel(id: string, targetValue: number, confirmed: boolean): Promise<CommandResult>;
  commandHorn(id: string, enabled: boolean, confirmed: boolean): Promise<CommandResult>;
};

export function createApiClient(opts: ApiClientOptions): ApiClient {
  const doFetch = opts.fetchImpl ?? fetch;
  const authHeaders = (): Record<string, string> =>
    opts.token ? { authorization: `Bearer ${opts.token}` } : {};

  async function getJson<T>(path: string): Promise<T> {
    const res = await doFetch(`${opts.baseUrl}${path}`, { headers: authHeaders() });
    if (!res.ok) throw new ApiError(`GET ${path} failed (${res.status})`, res.status);
    return (await res.json()) as T;
  }

  async function postCommand(path: string, body: unknown): Promise<CommandResult> {
    const res = await doFetch(`${opts.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    });
    // 202 accepted and 4xx rejections both return a structured CommandResult body.
    const data = (await res.json().catch(() => null)) as CommandResult | null;
    if (data && 'status' in data) return data;
    throw new ApiError(`POST ${path} failed (${res.status})`, res.status);
  }

  return {
    listSites: () => getJson<SiteSummary[]>('/api/sites'),
    getGateStatus: (id) => getJson<GateStatus>(`/api/gates/${encodeURIComponent(id)}/status`),
    commandLevel: (id, targetValue, confirmed) =>
      postCommand(`/api/gates/${encodeURIComponent(id)}/command-level`, { targetValue, confirmed }),
    commandHorn: (id, enabled, confirmed) =>
      postCommand(`/api/gates/${encodeURIComponent(id)}/horn`, { enabled, confirmed }),
  };
}
