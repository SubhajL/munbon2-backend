import { handler } from './getWaterLevelChart';

jest.mock('../shared/buildRepository', () => ({
  buildRepositoryFromEnv: jest.fn(() => ({})),
}));

jest.mock('../../src/services/water-level-chart-data.service', () => ({
  WaterLevelChartDataService: jest.fn().mockImplementation(() => ({
    getWaterLevelChartData: jest.fn(async () => ([
      {
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: 'AWD-1234',
        avg_level: 12.3,
        min_level: 10,
        max_level: 15,
        avg_quality: 95,
        sample_count: 3,
      },
    ])),
  })),
}));

jest.mock('../../src/transformers/water-level-chart-formatter', () => ({
  WaterLevelChartFormatter: jest.fn().mockImplementation(() => ({
    formatChartDataBySensor: jest.fn((rows: any, period: any, tz: string) => ({
      aggregation: { interval: '15 minutes', method: 'average' },
      period,
      timeRange: { start: 's', end: 'e' },
      localTimeZone: tz,
      sensors: { 'AWD-1234': { sensorId: 'AWD-1234', dataPoints: rows } },
      summary: { totalSensors: 1, totalDataPoints: rows.length },
    })),
  })),
}));

describe('getWaterLevelChart.handler', () => {
  test('returns 200 with formatted chart data', async () => {
    const res = await handler({ queryStringParameters: { period: '24h', timeZone: 'UTC' } });
    expect(res.statusCode).toBe(200);
    const body = JSON.parse(res.body);
    expect(body.period).toBe('24h');
    expect(body.sensors['AWD-1234']).toBeDefined();
  });

  test('returns 400 on invalid period', async () => {
    const res = await handler({ queryStringParameters: { period: 'invalid' } });
    expect(res.statusCode).toBe(400);
    const body = JSON.parse(res.body);
    expect(body.error).toContain('Invalid period');
  });
});

