import type {
  ControlAuthorityDashboard,
  MutationInput,
} from "./control-authority-proxy";

export type ControlAuthorityMutation = Omit<
  MutationInput,
  "accessToken" | "confirmation"
>;

export class ControlAuthorityApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ControlAuthorityApiError";
  }
}

export type ControlAuthorityClientOptions = {
  getToken?: () => string | undefined;
  onUnauthorized?: () => Promise<string | null>;
  fetchImpl?: typeof fetch;
};

export type ControlAuthorityClient = {
  read(planId: string, planVersion: number): Promise<ControlAuthorityDashboard>;
  mutate(
    input: ControlAuthorityMutation,
    confirmation: string,
    stepUpCode?: string,
  ): Promise<unknown>;
};

export function createControlAuthorityClient(
  options: ControlAuthorityClientOptions = {},
): ControlAuthorityClient {
  const fetchImpl = options.fetchImpl ?? fetch;

  async function request(
    path: string,
    init: RequestInit,
    token: string | undefined,
  ): Promise<Response> {
    return fetchImpl(path, {
      ...init,
      cache: "no-store",
      headers: {
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  }

  async function send(path: string, init: RequestInit): Promise<unknown> {
    let response = await request(path, init, options.getToken?.());
    if (response.status === 401 && options.onUnauthorized) {
      const refreshed = await options.onUnauthorized();
      if (refreshed) response = await request(path, init, refreshed);
    }
    if (!response.ok) {
      let message = `Control authority request failed (${response.status})`;
      try {
        const body = (await response.json()) as { error?: unknown };
        if (typeof body.error === "string") message = body.error;
      } catch {
        // A non-JSON failure remains a bounded status message.
      }
      throw new ControlAuthorityApiError(message, response.status);
    }
    return response.json();
  }

  return {
    read: (planId, planVersion) =>
      send(
        `/api/control-authority?${new URLSearchParams({
          planId,
          planVersion: String(planVersion),
        }).toString()}`,
        {},
      ) as Promise<ControlAuthorityDashboard>,
    mutate: (input, confirmation, stepUpCode) => {
      const headers: Record<string, string> = {
        "content-type": "application/json",
        "x-operator-confirmation": confirmation,
      };
      if (stepUpCode) headers["x-operator-step-up-code"] = stepUpCode;
      return send("/api/control-authority", {
        method: "POST",
        headers,
        body: JSON.stringify(input),
      });
    },
  };
}
