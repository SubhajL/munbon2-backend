interface CacheEntry<T> {
  value: T;
  expiry: number;
  lastAccess: number;
}

export interface CacheMetrics {
  hits: number;
  misses: number;
  evictions: number;
  size: number;
}

export class BoundedCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private timers = new Map<string, NodeJS.Timeout>();
  private hits = 0;
  private misses = 0;
  private evictions = 0;

  constructor(
    private readonly maxSize: number,
    private readonly defaultTTL: number = 60000,
  ) {}

  set(key: string, value: T, ttl: number = this.defaultTTL): void {
    const isUpdate = this.cache.has(key);

    if (!isUpdate && this.maxSize > 0 && this.cache.size >= this.maxSize) {
      this.evictLRU();
    }

    this.clearTimer(key);

    if (this.maxSize === 0) {
      return;
    }

    const expiry = Date.now() + ttl;
    const lastAccess = Date.now();
    this.cache.set(key, { value, expiry, lastAccess });

    const timer = setTimeout(() => {
      this.delete(key);
    }, ttl);
    this.timers.set(key, timer);
  }

  get(key: string): T | undefined {
    const entry = this.cache.get(key);

    if (!entry) {
      this.misses++;
      return undefined;
    }

    if (Date.now() > entry.expiry) {
      this.delete(key);
      this.misses++;
      return undefined;
    }

    entry.lastAccess = Date.now();
    this.hits++;
    return entry.value;
  }

  has(key: string): boolean {
    return this.get(key) !== undefined;
  }

  delete(key: string): boolean {
    this.clearTimer(key);
    return this.cache.delete(key);
  }

  clear(): void {
    this.timers.forEach((timer) => clearTimeout(timer));
    this.timers.clear();
    this.cache.clear();
    this.hits = 0;
    this.misses = 0;
    this.evictions = 0;
  }

  getMetrics(): CacheMetrics {
    return {
      hits: this.hits,
      misses: this.misses,
      evictions: this.evictions,
      size: this.cache.size,
    };
  }

  private evictLRU(): void {
    let oldestKey: string | undefined;
    let oldestAccess = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccess < oldestAccess) {
        oldestAccess = entry.lastAccess;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.delete(oldestKey);
      this.evictions++;
    }
  }

  private clearTimer(key: string): void {
    const timer = this.timers.get(key);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(key);
    }
  }
}

export class SimpleCache<T> extends BoundedCache<T> {
  constructor(defaultTTL: number = 60000) {
    super(Infinity, defaultTTL);
  }
}

// Cache decorator for methods
export function cacheable<T>(ttl: number = 60000) {
  const cache = new SimpleCache<T>();

  return function (
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor,
  ): PropertyDescriptor {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]): Promise<T> {
      const key = JSON.stringify([propertyKey, ...args]);

      const cached = cache.get(key);
      if (cached !== undefined) {
        return cached;
      }

      const result = await originalMethod.apply(this, args);
      cache.set(key, result, ttl);

      return result;
    };

    return descriptor;
  };
}
