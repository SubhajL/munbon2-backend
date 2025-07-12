import { Request, Response, NextFunction } from 'express';
import { randomUUID } from 'crypto';

export interface RequestIdOptions {
  headerName?: string;
  generator?: () => string;
  setResponseHeader?: boolean;
}

export const requestId = (options: RequestIdOptions = {}) => {
  const {
    headerName = 'x-request-id',
    generator = randomUUID,
    setResponseHeader = true
  } = options;

  return (req: Request, res: Response, next: NextFunction): void => {
    // Use existing request ID or generate new one
    const id = req.headers[headerName] as string || generator();
    
    // Set on request object
    req.headers[headerName] = id;
    
    // Optionally set on response
    if (setResponseHeader) {
      res.setHeader(headerName, id);
    }
    
    next();
  };
};