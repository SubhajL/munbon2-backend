import type { APIGatewayProxyResult } from '../types';
import pino from 'pino';
import { buildRepositoryFromEnv } from '../shared/buildRepository';
import { WaterLevelChartDataService } from '../../src/services/water-level-chart-data.service';
import { WaterLevelChartFormatter } from '../../src/transformers/water-level-chart-formatter';
import { isValidPeriod } from '../../src/utils/time-period.utils';

const logger = pino({ enabled: false });
const repository = buildRepositoryFromEnv(process.env);
const service = new WaterLevelChartDataService(repository as any, logger);
const formatter = new WaterLevelChartFormatter();

export async function handler(event: any): Promise<APIGatewayProxyResult> {
  try {
    const qs = event?.queryStringParameters || {};
    const period = (qs.period as string) || '24h';
    const sensorIdsParam = (qs.sensorIds as string) || '';
    const timeZone = (qs.timeZone as string) || 'UTC';

    if (!isValidPeriod(period)) {
      return {
        statusCode: 400,
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ error: `Invalid period: ${period}. Must be one of: 24h, 3d, 7d, 14d` }),
      };
    }

    const sensorIds = sensorIdsParam
      ? sensorIdsParam.split(',').map((s) => s.trim()).filter(Boolean)
      : undefined;

    const rows = await service.getWaterLevelChartData(period, sensorIds);
    const body = formatter.formatChartDataBySensor(rows, period as any, timeZone);

    return {
      statusCode: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    };
  } catch (err: any) {
    return {
      statusCode: 500,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ error: 'Internal Server Error', details: err?.message || String(err) }),
    };
  }
}

