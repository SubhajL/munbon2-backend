declare class CacheService {
    private client;
    private isConnected;
    connect(): Promise<void>;
    get(key: string): Promise<string | null>;
    set(key: string, value: string, ttl?: number): Promise<void>;
    delete(key: string): Promise<void>;
    disconnect(): Promise<void>;
}
export declare const cacheService: CacheService;
export {};
//# sourceMappingURL=cache.service.d.ts.map