declare class CacheService {
    private client;
    private isConnected;
    initialize(): Promise<void>;
    get(key: string): Promise<any>;
    set(key: string, value: any, ttl?: number): Promise<void>;
    delete(key: string): Promise<void>;
    clearPattern(pattern: string): Promise<void>;
    disconnect(): Promise<void>;
}
export declare const cacheService: CacheService;
export declare function initializeCache(): Promise<void>;
export {};
//# sourceMappingURL=cache.d.ts.map