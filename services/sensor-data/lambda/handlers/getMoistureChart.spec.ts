import { handler } from './getMoistureChart';

jest.mock('../shared/buildRepository', () => ({
  buildRepositoryFromEnv: jest.fn(() => ({})),
}));

jest.mock('../../src/services/moisture-chart-data.service', () => {
  return {
    MoistureChartDataService: jest.fn().mockImplementation(() => ({
      getMoistureChartData: jest.fn(async () => ([
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: '0001-0001',
          avg_moisture_surface: 45.5,
          min_moisture_surface: 40,
          max_moisture_surface: 50,
          avg_moisture_deep: 55.5,
          min_moisture_deep: 50,
          max_moisture_deep: 60,
          sample_count: 5,
        },
      ])),
    })),
  };
});

jest.mock('../../src/transformers/moisture-chart-formatter', () => ({
  MoistureChartFormatter: jest.fn().mockImplementation(() => ({
    formatChartDataBySensor: jest.fn((rows: any, period: any, tz: string) => ({
      aggregation: { interval: '15 minutes', method: 'average' },
      period,
      timeRange: { start: 's', end: 'e' },
      localTimeZone: tz,
      sensors: { '0001-0001': { sensorId: '0001-0001', dataPoints: rows } },
      summary: { totalSensors: 1, totalDataPoints: rows.length },
    })),
  })),
}));

describe('getMoistureChart.handler', () => {
  test('returns 200 with formatted chart data', async () => {
    const res = await handler({ queryStringParameters: { period: '24h', timeZone: 'UTC' } });
    expect(res.statusCode).toBe(200);
    const body = JSON.parse(res.body);
    expect(body.period).toBe('24h');
    expect(body.sensors['0001-0001']).toBeDefined();
  });

  test('returns 400 on invalid period', async () => {
    const res = await handler({ queryStringParameters: { period: 'bad' } });
    expect(res.statusCode).toBe(400);
    const body = JSON.parse(res.body);
    expect(body.error).toContain('Invalid period');
  });
});

