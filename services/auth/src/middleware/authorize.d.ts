import { Request, Response, NextFunction } from 'express';
export declare const authorize: (...permissions: string[]) => (req: Request, res: Response, next: NextFunction) => void;
export declare const authorizeRoles: (...roles: string[]) => (req: Request, res: Response, next: NextFunction) => void;
//# sourceMappingURL=authorize.d.ts.map