/**
 * Modbus register map for the Waste Way site, transcribed directly from
 * RID_MUNBON_SCADA_APP_SPEC.md. Addresses are used as-is with NO -1 offset.
 */

export type RegisterKind = 'holdingRegister' | 'coil';

export type RegisterPoint = {
  readonly name: PointName;
  readonly address: number;
  readonly kind: RegisterKind;
};

export type PointName = 'Gate_Level' | 'Door_SW' | 'Horn' | 'Op_gate' | 'GateCF';

export const REGISTERS = {
  Gate_Level: { name: 'Gate_Level', address: 104, kind: 'holdingRegister' },
  Door_SW: { name: 'Door_SW', address: 16, kind: 'coil' },
  Horn: { name: 'Horn', address: 15, kind: 'coil' },
  Op_gate: { name: 'Op_gate', address: 108, kind: 'holdingRegister' },
  GateCF: { name: 'GateCF', address: 17, kind: 'coil' },
} as const satisfies Record<PointName, RegisterPoint>;

/** Default Modbus unit id until the vendor confirms the real value (spec). */
export const DEFAULT_UNIT_ID = 1;
