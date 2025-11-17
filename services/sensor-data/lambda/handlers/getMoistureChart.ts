import type { APIGatewayProxyResult } from '../types';
import pino from 'pino';
import { buildRepositoryFromEnv } from '../shared/buildRepository';
import { MoistureChartDataService } from '../../src/services/moisture-chart-data.service';
import { MoistureChartFormatter } from '../../src/transformers/moisture-chart-formatter';
import { isValidPeriod } from '../../src/utils/time-period.utils';

const logger = pino({ enabled: false });
const repository = buildRepositoryFromEnv(process.env);
const service = new MoistureChartDataService(repository as any, logger);
const formatter = new MoistureChartFormatter();

export async function handler(event: any): Promise<APIGatewayProxyResult> {
  try {
    const qs = event?.queryStringParameters || {};
    const period = (qs.period as string) || '24h';
    const sensorIdsParam = (qs.sensorIds as string) || '';
    const timeZone = (qs.timeZone as string) || 'UTC';
    const includeSmoothed = String(qs.includeSmoothed || 'false').toLowerCase() === 'true';

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

    const rows = await service.getMoistureChartData(period, sensorIds, includeSmoothed);
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

