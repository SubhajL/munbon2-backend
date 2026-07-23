import type { GateStatus } from "./api";

export class ReadOnlyGateStatusError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ReadOnlyGateStatusError";
  }
}

export type ReadOnlyGateStatusClientOptions = {
  baseUrl: string;
  getToken: () => string | undefined;
  onUnauthorized?: () => Promise<string | null>;
  fetchImpl?: typeof fetch;
};

export type ReadOnlyGateStatusClient = {
  getGateStatus(id: string): Promise<GateStatus>;
};

type JsonObject = Record<string, unknown>;

const QUALITIES = new Set([
  "ok",
  "stale",
  "offline",
  "modbus_exception",
  "decode_error",
]);
const MARKER_COLORS = new Set(["green", "yellow", "red"]);

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isSnapshot(
  value: unknown,
  isDecodedValue: (candidate: unknown) => boolean,
): boolean {
  if (!isObject(value)) return false;
  return (
    (value.raw === null || typeof value.raw === "number") &&
    (value.value === null || isDecodedValue(value.value)) &&
    typeof value.quality === "string" &&
    QUALITIES.has(value.quality) &&
    isNullableString(value.lastUpdated) &&
    isNullableString(value.lastError)
  );
}

function isGateStatus(value: unknown): value is GateStatus {
  if (!isObject(value) || !isObject(value.endpoint)) return false;
  const endpoint = value.endpoint;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof endpoint.host === "string" &&
    typeof endpoint.port === "number" &&
    typeof endpoint.unitId === "number" &&
    typeof value.connection === "string" &&
    QUALITIES.has(value.connection) &&
    typeof value.markerColor === "string" &&
    MARKER_COLORS.has(value.markerColor) &&
    isNullableString(value.lastUpdated) &&
    isNullableString(value.lastError) &&
    isSnapshot(value.gateLevel, (candidate) => {
      if (!isObject(candidate)) return false;
      return (
        typeof candidate.level === "number" &&
        [1, 2, 3, 4].includes(candidate.level) &&
        typeof candidate.thaiLabel === "string" &&
        typeof candidate.technicalLabel === "string" &&
        typeof candidate.flowRate === "number"
      );
    }) &&
    isSnapshot(value.doorSw, (candidate) => {
      if (!isObject(candidate)) return false;
      return (
        typeof candidate.closed === "boolean" &&
        typeof candidate.thaiLabel === "string"
      );
    }) &&
    isSnapshot(value.horn, (candidate) => {
      if (!isObject(candidate)) return false;
      return (
        typeof candidate.on === "boolean" &&
        typeof candidate.thaiLabel === "string"
      );
    }) &&
    isSnapshot(value.gateCf, (candidate) => {
      if (!isObject(candidate)) return false;
      return typeof candidate.confirmed === "boolean";
    })
  );
}

export function createReadOnlyGateStatusClient(
  options: ReadOnlyGateStatusClientOptions,
): ReadOnlyGateStatusClient {
  const fetchStatus = options.fetchImpl ?? fetch;
  const headers = (token: string | undefined): Record<string, string> =>
    token ? { authorization: `Bearer ${token}` } : {};

  async function send(path: string, token: string | undefined) {
    return fetchStatus(`${options.baseUrl}${path}`, {
      headers: headers(token),
    });
  }

  return {
    async getGateStatus(id) {
      const path = `/api/gates/${encodeURIComponent(id)}/status`;
      const initialToken = options.getToken();
      if (!initialToken) {
        throw new ReadOnlyGateStatusError(
          `GET ${path} blocked without bearer`,
          401,
        );
      }
      let response = await send(path, initialToken);
      if (response.status === 401 && options.onUnauthorized) {
        const refreshedToken = await options.onUnauthorized();
        if (refreshedToken) {
          response = await send(path, refreshedToken);
        }
      }
      if (!response.ok) {
        throw new ReadOnlyGateStatusError(
          `GET ${path} failed (${response.status})`,
          response.status,
        );
      }
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        throw new ReadOnlyGateStatusError(
          `GET ${path} returned invalid JSON`,
          502,
        );
      }
      if (!isGateStatus(body)) {
        throw new ReadOnlyGateStatusError(
          `GET ${path} returned malformed gate status`,
          502,
        );
      }
      return body;
    },
  };
}
