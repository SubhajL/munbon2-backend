import express, { type Express, type NextFunction, type Request, type Response } from 'express';
import { logger } from '../utils/logger';
import { buildInternalRouter } from './internal-routes';
import { buildRouter, type ApiDeps } from './routes';

const CLIENT_ERROR_MESSAGES: Record<number, string> = {
  400: 'malformed request body',
  413: 'payload too large',
  415: 'unsupported media type',
};

/** Builds the Express app (does not listen) so it can be driven by supertest. Body
 * parsing is scoped PER ROUTER (/api at 2kb, the /internal validate route at 8kb) rather
 * than globally, so a full command-intent body is not rejected by the tiny command cap. */
export function buildServer(deps: ApiDeps): Express {
  const app = express();

  app.get('/health', (_req, res) => {
    res.json({ status: 'healthy', service: 'scada-gate-control' });
  });

  // Prometheus scrape endpoint — unauthenticated (like /health), read-only, no body parser.
  // It exposes only aggregate operational counts (write/rejection volume), never gate values
  // or credentials. DEPLOY NOTE: like any Prometheus target, restrict reachability at the
  // network layer (bind the scrape port to the internal monitoring interface); do not expose
  // it to untrusted networks.
  app.get('/metrics', async (_req, res, next) => {
    try {
      res.set('Content-Type', deps.metrics.contentType);
      res.send(await deps.metrics.render());
    } catch (error) {
      next(error);
    }
  });

  app.use('/api', buildRouter(deps));
  app.use('/internal', buildInternalRouter(deps));

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  app.use((error: unknown, req: Request, res: Response, _next: NextFunction) => {
    // Honor body-parser client errors (malformed/oversized JSON carry a 4xx `status`);
    // everything else is a genuine internal failure.
    const raw =
      (error as { status?: unknown; statusCode?: unknown; type?: unknown } | null) ?? null;
    const claimed =
      typeof raw?.status === 'number'
        ? raw.status
        : typeof raw?.statusCode === 'number'
          ? raw.statusCode
          : 500;
    // Honor a 4xx ONLY for a body-parser error (those carry a string `type`, e.g.
    // 'entity.parse.failed'/'entity.too.large'). A DB/programming error that happens to
    // carry a sub-500 status is still an internal failure -> 500. Never emit 2xx/3xx.
    const isClientError = typeof raw?.type === 'string' && claimed >= 400 && claimed < 500;
    const errMsg = error instanceof Error ? error.message : String(error);
    if (!isClientError) {
      logger.error({ err: errMsg, path: req.path }, 'unhandled API error');
      res.status(500).json({ error: 'internal error' }); // do not leak internals
      return;
    }
    // Log client errors too (previously silent): a flood of malformed/oversized bodies at
    // the machine boundary should be visible to log-based alerting.
    logger.warn({ err: errMsg, path: req.path, status: claimed }, 'rejected client request');
    res.status(claimed).json({ error: CLIENT_ERROR_MESSAGES[claimed] ?? 'bad request' });
  });

  return app;
}
