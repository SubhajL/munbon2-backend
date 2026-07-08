/**
 * Branded primitive helper. Prevents mixing raw strings/numbers that share a
 * structural type but mean different things (e.g. a GateId vs a SiteId).
 */
export type Brand<T, B extends string> = T & { readonly __brand: B };

export type GateId = Brand<string, 'GateId'>;
export type SiteId = Brand<string, 'SiteId'>;

export const toGateId = (value: string): GateId => value as GateId;
export const toSiteId = (value: string): SiteId => value as SiteId;
