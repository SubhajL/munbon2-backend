import { WaterLevelChartDataService } from './water-level-chart-data.service';
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

describe('WaterLevelChartDataService', () => {
  let service: WaterLevelChartDataService;

  beforeEach(() => {
    jest.clearAllMocks();
    service = new WaterLevelChartDataService(mockRepository, mockLogger);
  });

  describe('getWaterLevelChartData', () => {
    it('queries correct time range for 24h period', async () => {
      const mockRows = [
        {
          time: '2025-11-03T12:00:00Z',
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 96,
        },
      ];

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const result = await service.getWaterLevelChartData('24h');

      expect(mockRepository.query).toHaveBeenCalled();
      expect(result).toEqual(mockRows);
      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];

      expect(params).toHaveLength(2);
      const [startDate, endDate] = params;
      const diffMs = endDate.getTime() - startDate.getTime();
      expect(Math.abs(diffMs - 86400000)).toBeLessThan(1000);
    });

    it('queries correct time range for 7d period', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getWaterLevelChartData('7d');

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      const [startDate, endDate] = params;
      const diffMs = endDate.getTime() - startDate.getTime();
      expect(Math.abs(diffMs - 604800000)).toBeLessThan(1000);
    });

    it('includes sensor filter when IDs provided', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getWaterLevelChartData('24h', [
        'AWD-B89D',
        'AWD-558F',
        'AWD-A4F8',
      ]);

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];

      expect(params).toHaveLength(3);
      const sensorIds = params[2];

      expect(sensorIds).toContain('AWD-B89D');
      expect(sensorIds).toContain('AWD-558F');
      expect(sensorIds).toContain('AWD-A4F8');
    });

    it('accepts AWD format sensor IDs unchanged', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getWaterLevelChartData('24h', ['AWD-B89D']);

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      const sensorIds = params[2];

      expect(sensorIds).toContain('AWD-B89D');
    });

    it('returns empty array when no readings exist', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      const result = await service.getWaterLevelChartData('24h');

      expect(result).toEqual([]);
    });

    it('returns rows ordered by time ascending', async () => {
      const mockRows = [
        {
          time: '2025-11-02T12:00:00Z',
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95,
          sample_count: 96,
        },
        {
          time: '2025-11-03T12:00:00Z',
          sensor_id: 'AWD-B89D',
          avg_level: 127.5,
          min_level: 122,
          max_level: 132,
          avg_quality: 96,
          sample_count: 96,
        },
      ];

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const result = await service.getWaterLevelChartData('24h');

      expect(result).toHaveLength(2);
      expect(result[0].time).toBe('2025-11-02T12:00:00Z');
      expect(result[1].time).toBe('2025-11-03T12:00:00Z');
    });

    it('throws on invalid period', async () => {
      await expect(
        service.getWaterLevelChartData('invalid' as any)
      ).rejects.toThrow();
    });

    it('builds SQL with 15-minute time_bucket aggregation', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await service.getWaterLevelChartData('24h');

      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const sql = callArgs[0];

      expect(sql).toContain("time_bucket('15 minutes'");
      expect(sql).toContain('AVG(level_cm)');
      expect(sql).toContain('MIN(level_cm)');
      expect(sql).toContain('MAX(level_cm)');
      expect(sql).toContain('AVG(quality_score)');
      expect(sql).toContain('COUNT(*)');
      expect(sql).toContain('GROUP BY');
      expect(sql).toContain('ORDER BY time ASC');
    });
  });

});
