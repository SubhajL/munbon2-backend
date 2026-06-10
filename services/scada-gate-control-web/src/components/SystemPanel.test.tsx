import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, test } from 'vitest';
import { SystemPanel } from './SystemPanel';

describe('SystemPanel', () => {
  test('renders the system title and per-status connection counts', () => {
    render(<SystemPanel summary={{ online: 2, stale: 1, offline: 0 }} />);
    expect(screen.getByRole('heading', { name: /มูลบน เฟส 2/ })).toBeInTheDocument();
    expect(screen.getByTestId('status-pill-online')).toHaveTextContent('2');
    expect(screen.getByTestId('status-pill-stale')).toHaveTextContent('1');
    expect(screen.getByTestId('status-pill-offline')).toHaveTextContent('0');
  });

  test('shows an error alert (not counts) when the API is unreachable', () => {
    render(<SystemPanel summary={{ online: 0, stale: 0, offline: 0 }} error="HTTP 500" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the gate API');
    expect(screen.queryByTestId('status-pill-online')).not.toBeInTheDocument();
  });

  test('has no accessibility violations', async () => {
    const { container } = render(<SystemPanel summary={{ online: 1, stale: 0, offline: 0 }} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
