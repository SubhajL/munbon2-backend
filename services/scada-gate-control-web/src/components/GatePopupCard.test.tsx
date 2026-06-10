import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { describe, expect, test, vi } from 'vitest';
import { GatePopupCard } from './GatePopupCard';
import type { GateStatus } from '@/lib/api';

const status: GateStatus = {
  id: 'waste-way',
  name: 'Waste Way',
  endpoint: { host: 'h', port: 502, unitId: 1 },
  connection: 'ok',
  markerColor: 'green',
  lastUpdated: '2024-01-01T00:00:00.000Z',
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

describe('GatePopupCard', () => {
  test('renders decoded gate level, flow rate and the last-updated time', () => {
    render(<GatePopupCard status={status} onDetail={() => {}} />);
    expect(screen.getByTestId('gate-popup')).toHaveTextContent('เปิดระดับ 1 — 0.5 ลบ.ม./วินาที');
    expect(screen.getByText('07:00:00')).toBeInTheDocument();
  });

  test('shows a loading state when status is not yet available', () => {
    render(<GatePopupCard status={null} loading onDetail={() => {}} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  test('fires onDetail when the control button is clicked', async () => {
    const onDetail = vi.fn();
    render(<GatePopupCard status={status} onDetail={onDetail} />);
    await userEvent.click(screen.getByRole('button', { name: /ดูรายละเอียด/ }));
    expect(onDetail).toHaveBeenCalledOnce();
  });

  test('has no accessibility violations', async () => {
    const { container } = render(<GatePopupCard status={status} onDetail={() => {}} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
