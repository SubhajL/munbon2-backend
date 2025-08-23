import { Request, Response, NextFunction } from 'express';
declare class SpatialController {
    queryByBounds(req: Request, res: Response, next: NextFunction): Promise<void>;
    queryByDistance(req: Request, res: Response, next: NextFunction): Promise<void>;
    queryByIntersection(req: Request, res: Response, next: NextFunction): Promise<void>;
    buffer(req: Request, res: Response, next: NextFunction): Promise<void>;
    union(req: Request, res: Response, next: NextFunction): Promise<void>;
    intersection(req: Request, res: Response, next: NextFunction): Promise<void>;
    simplify(req: Request, res: Response, next: NextFunction): Promise<void>;
    transform(req: Request, res: Response, next: NextFunction): Promise<void>;
    calculateArea(req: Request, res: Response, next: NextFunction): Promise<void>;
    calculateLength(req: Request, res: Response, next: NextFunction): Promise<void>;
    calculateDistance(req: Request, res: Response, next: NextFunction): Promise<void>;
    getElevation(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const spatialController: SpatialController;
export {};
//# sourceMappingURL=spatial.controller.d.ts.map