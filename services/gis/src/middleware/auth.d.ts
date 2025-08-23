import { Request, Response, NextFunction } from 'express';
interface JwtPayload {
    id: string;
    email: string;
    roles: string[];
}
declare global {
    namespace Express {
        interface Request {
            user?: JwtPayload;
        }
    }
}
export declare const authenticate: (req: Request, res: Response, next: NextFunction) => Promise<void>;
export declare const authenticateJWT: (req: Request, res: Response, next: NextFunction) => Promise<void>;
export {};
//# sourceMappingURL=auth.d.ts.map