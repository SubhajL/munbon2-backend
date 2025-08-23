import { Pool } from 'pg';
export declare const connectDatabases: () => Promise<void>;
export declare const getPostgresPool: () => Pool;
export declare const getTimescalePool: () => Pool;
export declare const executeQuery: (pool: Pool, query: string, params?: any[], schema?: string) => Promise<any>;
export declare const closeDatabases: () => Promise<void>;
//# sourceMappingURL=database.d.ts.map