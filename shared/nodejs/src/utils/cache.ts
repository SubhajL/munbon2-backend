interface CacheEntry<T> {
  value: T;
  expiry: number;
}

export class SimpleCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private timers = new Map<string, NodeJS.Timeout>();

  constructor(private readonly defaultTTL: number = 60000) {} // 1 minute default

  set(key: string, value: T, ttl: number = this.defaultTTL): void {
    // Clear existing timer if any
    this.clearTimer(key);

    const expiry = Date.now() + ttl;
    this.cache.set(key, { value, expiry });

    // Set auto-cleanup timer
    const timer = setTimeout(() => {
      this.delete(key);
    }, ttl);
    this.timers.set(key, timer);
  }

  get(key: string): T | undefined {
    const entry = this.cache.get(key);
    
    if (!entry) {
      return undefined;
    }

    if (Date.now() > entry.expiry) {
      this.delete(key);
      return undefined;
    }

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
    // Clear all timers
    this.timers.forEach(timer => clearTimeout(timer));
    this.timers.clear();
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }

  private clearTimer(key: string): void {
    const timer = this.timers.get(key);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(key);
    }
  }
}

// Cache decorator for methods
export function cacheable<T>(ttl: number = 60000) {
  const cache = new SimpleCache<T>();

  return function(
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ): PropertyDescriptor {
    const originalMethod = descriptor.value;

    descriptor.value = async function(...args: any[]): Promise<T> {
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