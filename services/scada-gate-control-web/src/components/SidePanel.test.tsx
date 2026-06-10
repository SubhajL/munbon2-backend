import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test, vi } from 'vitest';
import { SidePanel } from './SidePanel';
import type { GateStatus } from '@/lib/api';

const status: GateStatus = {
  id: 'waste-way',
  name: 'Waste Way',
  endpoint: { host: '172.16.1.103', port: 502, unitId: 1 },
  connection: 'ok',
  markerColor: 'green',
  lastUpdated: null,
  lastError: null,
  gateLevel: {
    raw: 2,
    value: { level: 2, thaiLabel: 'เปิดระดับ 1', technicalLabel: 'Level 2', flowRate: 0.5 },
    quality: 'ok',
    lastUpdated: null,
    lastError: null,
  },
  doorSw: { raw: 1, value: { closed: true, thaiLabel: 'ปิด' }, quality: 'ok', lastUpdated: null, lastError: null },
  horn: { raw: 0, value: { on: false, thaiLabel: 'ปิด' }, quality: 'ok', lastUpdated: null, lastError: null },
  gateCf: { raw: 0, value: { confirmed: false }, quality: 'ok', lastUpdated: null, lastError: null },
};

describe('SidePanel', () => {
  test('shows Door_SW status-only plus the raw gate level and Modbus endpoint', () => {
    render(<SidePanel status={status} canCommand onHorn={() => {}} />);
    expect(screen.getByText(/Door_SW/)).toBeInTheDocument();
    expect(screen.getByText('Modbus 172.16.1.103:502')).toBeInTheDocument();
    expect(screen.getByText('Unit ID: 1')).toBeInTheDocument();
  });

  test('operator horn buttons fire onHorn with the right state', async () => {
    const onHorn = vi.fn();
    render(<SidePanel status={status} canCommand onHorn={onHorn} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'เปิดไซเรน' }));
    expect(onHorn).toHaveBeenCalledWith(true);
    await user.click(screen.getByRole('button', { name: 'ปิดไซเรน' }));
    expect(onHorn).toHaveBeenCalledWith(false);
  });

  test('a viewer cannot operate the horn', () => {
    render(<SidePanel status={status} canCommand={false} onHorn={() => {}} />);
    expect(screen.getByRole('button', { name: 'เปิดไซเรน' })).toBeDisabled();
    expect(screen.getByText(/Viewer — read only/)).toBeInTheDocument();
  });
});
