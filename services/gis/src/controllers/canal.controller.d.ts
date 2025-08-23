import { Request, Response, NextFunction } from 'express';
declare class CanalController {
    getAllCanals(req: Request, res: Response, next: NextFunction): Promise<void>;
    getCanalById(req: Request, res: Response, next: NextFunction): Promise<void>;
    queryCanals(req: Request, res: Response, next: NextFunction): Promise<void>;
    getFlowHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    getConnectedGates(req: Request, res: Response, next: NextFunction): Promise<void>;
    getNetworkTopology(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateCanalStatus(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateFlowRate(req: Request, res: Response, next: NextFunction): Promise<void>;
    getMaintenanceHistory(req: Request, res: Response, next: NextFunction): Promise<void>;
    createCanal(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateCanal(req: Request, res: Response, next: NextFunction): Promise<void>;
    updateCanalGeometry(req: Request, res: Response, next: NextFunction): Promise<void>;
    deleteCanal(req: Request, res: Response, next: NextFunction): Promise<void>;
    analyzeNetwork(req: Request, res: Response, next: NextFunction): Promise<void>;
    optimizeFlow(req: Request, res: Response, next: NextFunction): Promise<void>;
    identifyBottlenecks(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkImportCanals(req: Request, res: Response, next: NextFunction): Promise<void>;
    bulkUpdateCanals(req: Request, res: Response, next: NextFunction): Promise<void>;
}
export declare const canalController: CanalController;
export {};
//# sourceMappingURL=canal.controller.d.ts.map