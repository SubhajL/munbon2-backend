import { Request, Response, NextFunction } from 'express';
interface CacheOptions {
    ttl?: number;
    keyGenerator?: (req: Request) => string;
}
export declare const cacheMiddleware: (options?: CacheOptions) => (req: Request, res: Response, next: NextFunction) => Promise<void>;
export {};
//# sourceMappingURL=cache.d.ts.map