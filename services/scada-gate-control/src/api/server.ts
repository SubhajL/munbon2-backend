import express, { type Express, type NextFunction, type Request, type Response } from 'express';
import { logger } from '../utils/logger';
import { buildRouter, type ApiDeps } from './routes';

/** Builds the Express app (does not listen) so it can be driven by supertest. */
export function buildServer(deps: ApiDeps): Express {
  const app = express();
  app.use(express.json({ limit: '2kb' })); // command bodies are tiny

  app.get('/health', (_req, res) => {
    res.json({ status: 'healthy', service: 'scada-gate-control' });
  });

  app.use('/api', buildRouter(deps));

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  app.use((error: unknown, req: Request, res: Response, _next: NextFunction) => {
    logger.error(
      { err: error instanceof Error ? error.message : String(error), path: req.path },
      'unhandled API error',
    );
    res.status(500).json({ error: 'internal error' }); // do not leak internals
  });

  return app;
}
