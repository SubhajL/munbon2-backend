import { MoistureChartDataService } from './moisture-chart-data.service';
import { TimescaleRepository } from '../repository/timescale.repository';
import { Logger } from 'pino';

const mockRepository = {
  query: jest.fn(),
} as unknown as TimescaleRepository;

const mockLogger = {
  error: jest.fn(),
  warn: jest.fn(),
  info: jest.fn(),
} as unknown as Logger;

describe('MoistureChartDataService', () => {
  let service: MoistureChartDataService;

  beforeEach(() => {
    jest.clearAllMocks();
    service = new MoistureChartDataService(mockRepository, mockLogger);
  });

  describe('getMoistureChartData', () => {
    it('queries correct time range for 24h period', async () => {
      const mockRows = [
        {
          time: '2025-11-03T12:00:00Z',
          sensor_id: 'MS-00001-00001',
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 96,
        },
      ];

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const result = await service.getMoistureChartData('24h');

      expect(mockRepository.query).toHaveBeenCalled();
      expect(result).toEqual(mockRows);
      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];

      // Verify time range parameters (start, end)
      expect(params).toHaveLength(2);
      const [startDate, endDate] = params;
      const diffMs = endDate.getTime() - startDate.getTime();
      expect(Math.abs(diffMs - 86400000)).toBeLessThan(1000); // 24 hours
    });

    it('queries correct time range for 7d period', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getMoistureChartData('7d');

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      const [startDate, endDate] = params;
      const diffMs = endDate.getTime() - startDate.getTime();
      expect(Math.abs(diffMs - 604800000)).toBeLessThan(1000); // 7 days
    });

    it('normalizes short form sensor IDs to full form', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getMoistureChartData('24h', ['0001-0001', '0002-0003']);

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];

      // Should have [startDate, endDate, normalizedIds]
      expect(params).toHaveLength(3);
      const normalizedIds = params[2];

      expect(normalizedIds).toContain('MS-00001-00001');
      expect(normalizedIds).toContain('MS-00002-00003');
    });

    it('accepts full form sensor IDs unchanged', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getMoistureChartData('24h', ['MS-00001-00001']);

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      const normalizedIds = params[2];

      expect(normalizedIds).toContain('MS-00001-00001');
    });

    it('returns empty array when no readings exist', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      const result = await service.getMoistureChartData('24h');

      expect(result).toEqual([]);
    });

    it('returns rows ordered by time ascending', async () => {
      const mockRows = [
        {
          time: '2025-11-02T12:00:00Z',
          sensor_id: 'MS-00001-00001',
          avg_moisture_surface: 65.5,
        },
        {
          time: '2025-11-03T12:00:00Z',
          sensor_id: 'MS-00001-00001',
          avg_moisture_surface: 66.5,
        },
      ];

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const result = await service.getMoistureChartData('24h');

      expect(result).toHaveLength(2);
      expect(result[0].time).toBe('2025-11-02T12:00:00Z');
      expect(result[1].time).toBe('2025-11-03T12:00:00Z');
    });

    it('handles mix of short and full form sensor IDs', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getMoistureChartData('24h', [
        '0001-0001',
        'MS-00002-0003',
        '0003-0004',
      ]);

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      const normalizedIds = params[2];

      expect(normalizedIds).toContain('MS-00001-00001');
      expect(normalizedIds).toContain('MS-00002-0003');
      expect(normalizedIds).toContain('MS-00003-00004');
    });

    it('throws on invalid period', async () => {
      await expect(
        service.getMoistureChartData('invalid' as any)
      ).rejects.toThrow();
    });
  });

  describe('normalizeSensorIds', () => {
    it('converts short form 0001-0001 to MS-00001-00001', () => {
      const result = service.normalizeSensorIds(['0001-0001']);
      expect(result).toContain('MS-00001-00001');
    });

    it('converts short form 1-1 to MS-00001-00001', () => {
      const result = service.normalizeSensorIds(['1-1']);
      expect(result).toContain('MS-00001-00001');
    });

    it('keeps full form IDs unchanged', () => {
      const result = service.normalizeSensorIds(['MS-00001-00001']);
      expect(result).toContain('MS-00001-00001');
    });

    it('normalizes 12 moisture sensors 0001-0001 to 0001-0012', () => {
      const shortIds = [
        '0001-0001',
        '0001-0002',
        '0001-0003',
        '0001-0004',
        '0001-0005',
        '0001-0006',
        '0001-0007',
        '0001-0008',
        '0001-0009',
        '0001-0010',
        '0001-0011',
        '0001-0012',
      ];

      const result = service.normalizeSensorIds(shortIds);

      expect(result).toHaveLength(12);
      expect(result[0]).toBe('MS-00001-00001');
      expect(result[11]).toBe('MS-00001-00012');
    });

    it('returns empty array for empty input', () => {
      const result = service.normalizeSensorIds([]);
      expect(result).toEqual([]);
    });

    it('handles mixed formats in single call', () => {
      const result = service.normalizeSensorIds([
        '0001-0001',
        'MS-00001-0002',
        '1-3',
      ]);

      expect(result).toContain('MS-00001-00001');
      expect(result).toContain('MS-00001-0002');
      expect(result).toContain('MS-00001-00003');
    });
  });
});
