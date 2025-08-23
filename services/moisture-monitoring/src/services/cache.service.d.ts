export declare class CacheService {
    private redis;
    private defaultTTL;
    constructor();
    get<T>(key: string): Promise<T | null>;
    set(key: string, value: any, ttl?: number): Promise<void>;
    delete(key: string): Promise<void>;
    deletePattern(pattern: string): Promise<void>;
    invalidateSensorCache(sensorId: string): Promise<void>;
    publish(channel: string, message: any): Promise<void>;
    subscribe(channel: string, callback: (message: any) => void): Promise<void>;
    close(): Promise<void>;
}
//# sourceMappingURL=cache.service.d.ts.map