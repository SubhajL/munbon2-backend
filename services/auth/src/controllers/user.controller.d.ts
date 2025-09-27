import { Request, Response, NextFunction } from 'express';
declare class UserController {
    getProfile(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateProfile(req: Request, res: Response, next: NextFunction): Promise<void>;
    deleteAccount(req: Request, res: Response, next: NextFunction): Promise<void>;
    getUsers(req: Request, res: Response, next: NextFunction): Promise<void>;
    getUser(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateUser(req: Request, res: Response, next: NextFunction): Promise<void>;
    deleteUser(req: Request, res: Response, next: NextFunction): Promise<void>;
    lockUser(req: Request, res: Response, next: NextFunction): Promise<void>;
    unlockUser(req: Request, res: Response, next: NextFunction): Promise<void>;
    assignRole(req: Request, res: Response, next: NextFunction): Promise<void>;
    revokeRole(req: Request, res: Response, next: NextFunction): Promise<void>;
    getUserAuditLogs(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const userController: UserController;
export {};
//# sourceMappingURL=user.controller.d.ts.map