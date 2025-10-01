import { describe, expect, test, beforeEach, vi } from "vitest";
import { BoundedCache } from "./cache";

describe("BoundedCache", () => {
  describe("eviction", () => {
    test("evicts LRU entry when max size exceeded", () => {
      const cache = new BoundedCache<string>(2);

      cache.set("key1", "value1");
      cache.set("key2", "value2");
      cache.set("key3", "value3");

      expect(cache.get("key1")).toBeUndefined();
      expect(cache.get("key2")).toBe("value2");
      expect(cache.get("key3")).toBe("value3");
    });

    test("updates access time on get operations", () => {
      const cache = new BoundedCache<string>(2);

      cache.set("key1", "value1");
      cache.set("key2", "value2");
      cache.get("key1");
      cache.set("key3", "value3");

      expect(cache.get("key1")).toBe("value1");
      expect(cache.get("key2")).toBeUndefined();
    });
  });

  describe("expiration", () => {
    test("respects TTL expiration", async () => {
      const cache = new BoundedCache<string>(10, 50);

      cache.set("key1", "value1");
      expect(cache.get("key1")).toBe("value1");

      await new Promise((resolve) => setTimeout(resolve, 60));
      expect(cache.get("key1")).toBeUndefined();
    });

    test("custom TTL overrides default", async () => {
      const cache = new BoundedCache<string>(10, 100);

      cache.set("short", "value", 20);
      cache.set("long", "value", 200);

      await new Promise((resolve) => setTimeout(resolve, 30));

      expect(cache.get("short")).toBeUndefined();
      expect(cache.get("long")).toBe("value");
    });
  });

  describe("metrics", () => {
    test("tracks hit and miss metrics", () => {
      const cache = new BoundedCache<string>(10);

      cache.set("key1", "value1");
      cache.get("key1");
      cache.get("key2");
      cache.get("key1");

      const metrics = cache.getMetrics();
      expect(metrics.hits).toBe(2);
      expect(metrics.misses).toBe(1);
    });

    test("tracks eviction count", () => {
      const cache = new BoundedCache<string>(2);

      cache.set("key1", "value1");
      cache.set("key2", "value2");
      cache.set("key3", "value3");
      cache.set("key4", "value4");

      const metrics = cache.getMetrics();
      expect(metrics.evictions).toBe(2);
    });

    test("tracks current size", () => {
      const cache = new BoundedCache<string>(5);

      expect(cache.getMetrics().size).toBe(0);

      cache.set("key1", "value1");
      cache.set("key2", "value2");

      expect(cache.getMetrics().size).toBe(2);
    });
  });

  describe("boundary conditions", () => {
    test("allows size zero for disabled caching", () => {
      const cache = new BoundedCache<string>(0);

      cache.set("key1", "value1");
      expect(cache.get("key1")).toBeUndefined();
      expect(cache.getMetrics().size).toBe(0);
    });

    test("clear resets all metrics and entries", () => {
      const cache = new BoundedCache<string>(5);

      cache.set("key1", "value1");
      cache.set("key2", "value2");
      cache.get("key1");
      cache.get("missing");

      cache.clear();

      const metrics = cache.getMetrics();
      expect(metrics.size).toBe(0);
      expect(metrics.hits).toBe(0);
      expect(metrics.misses).toBe(0);
      expect(metrics.evictions).toBe(0);
      expect(cache.get("key1")).toBeUndefined();
    });
  });

  describe("replacement", () => {
    test("updating existing key does not increase size", () => {
      const cache = new BoundedCache<string>(2);

      cache.set("key1", "value1");
      cache.set("key1", "updated");
      cache.set("key2", "value2");

      expect(cache.getMetrics().size).toBe(2);
      expect(cache.get("key1")).toBe("updated");
    });
  });
});
