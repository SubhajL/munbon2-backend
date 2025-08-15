#!/usr/bin/env python3
"""Performance benchmarking suite for Gravity Optimizer"""

import asyncio
import httpx
import time
import statistics
import json
from datetime import datetime
from typing import List, Dict
import sys
import os

# Configuration
BASE_URL = os.getenv("GRAVITY_API_URL", "http://localhost:3020")
API_PREFIX = "/api/v1/gravity-optimizer"


class PerformanceBenchmark:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "tests": {}
        }
        
    async def run_all_benchmarks(self):
        """Run complete benchmark suite"""
        print("Gravity Optimizer Performance Benchmark")
        print("=" * 50)
        print(f"Target: {BASE_URL}")
        print(f"Started: {self.results['timestamp']}")
        print("=" * 50)
        
        # Test 1: Health check latency
        await self.benchmark_health_check()
        
        # Test 2: Single zone feasibility
        await self.benchmark_single_zone_feasibility()
        
        # Test 3: Multi-zone feasibility
        await self.benchmark_multi_zone_feasibility()
        
        # Test 4: Full optimization - small
        await self.benchmark_optimization_small()
        
        # Test 5: Full optimization - large
        await self.benchmark_optimization_large()
        
        # Test 6: Concurrent requests
        await self.benchmark_concurrent_requests()
        
        # Test 7: Flow split optimization
        await self.benchmark_flow_split()
        
        # Test 8: Large scale simulation
        await self.benchmark_large_scale()
        
        # Generate report
        self.generate_report()
        
    async def benchmark_health_check(self, iterations: int = 100):
        """Benchmark health check endpoint"""
        print("\n1. Health Check Latency Test")
        print("-" * 30)
        
        url = f"{BASE_URL}/health"
        times = []
        
        async with httpx.AsyncClient() as client:
            # Warmup
            await client.get(url)
            
            for i in range(iterations):
                start = time.time()
                response = await client.get(url)
                elapsed = (time.time() - start) * 1000  # ms
                times.append(elapsed)
                
                if i % 20 == 0:
                    print(f"  Progress: {i}/{iterations}")
        
        self.results["tests"]["health_check"] = {
            "iterations": iterations,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "p95_ms": sorted(times)[int(0.95 * len(times))],
            "p99_ms": sorted(times)[int(0.99 * len(times))]
        }
        
        print(f"  Mean: {self.results['tests']['health_check']['mean_ms']:.2f} ms")
        print(f"  P95: {self.results['tests']['health_check']['p95_ms']:.2f} ms")
        
    async def benchmark_single_zone_feasibility(self, iterations: int = 50):
        """Benchmark single zone feasibility check"""
        print("\n2. Single Zone Feasibility Test")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/feasibility/zone_3"
        params = {"required_flow": 15.0, "source_water_level": 222.0}
        times = []
        
        async with httpx.AsyncClient() as client:
            for i in range(iterations):
                start = time.time()
                response = await client.get(url, params=params)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                if i % 10 == 0:
                    print(f"  Progress: {i}/{iterations}")
        
        self.results["tests"]["single_zone_feasibility"] = self._calculate_stats(times, iterations)
        print(f"  Mean: {self.results['tests']['single_zone_feasibility']['mean_ms']:.2f} ms")
        
    async def benchmark_multi_zone_feasibility(self, iterations: int = 30):
        """Benchmark multi-zone feasibility check"""
        print("\n3. Multi-Zone Feasibility Test (6 zones)")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/feasibility/check"
        data = {
            "zone_requests": [
                {"zone_id": f"zone_{i}", "required_flow_rate": 10.0 + i, "priority": 1}
                for i in range(1, 7)
            ],
            "source_water_level": 222.0
        }
        times = []
        
        async with httpx.AsyncClient() as client:
            for i in range(iterations):
                start = time.time()
                response = await client.post(url, json=data)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                if i % 10 == 0:
                    print(f"  Progress: {i}/{iterations}")
        
        self.results["tests"]["multi_zone_feasibility"] = self._calculate_stats(times, iterations)
        print(f"  Mean: {self.results['tests']['multi_zone_feasibility']['mean_ms']:.2f} ms")
        
    async def benchmark_optimization_small(self, iterations: int = 20):
        """Benchmark optimization with 3 zones"""
        print("\n4. Small Optimization Test (3 zones)")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/optimize"
        data = {
            "zone_requests": [
                {"zone_id": "zone_1", "required_volume": 20000, "required_flow_rate": 15.0, "priority": 1},
                {"zone_id": "zone_2", "required_volume": 15000, "required_flow_rate": 12.0, "priority": 1},
                {"zone_id": "zone_3", "required_volume": 10000, "required_flow_rate": 8.0, "priority": 2}
            ],
            "source_water_level": 222.0,
            "objective": "BALANCED",
            "include_contingency": False,
            "include_energy_recovery": False
        }
        times = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(iterations):
                start = time.time()
                response = await client.post(url, json=data)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                print(f"  Iteration {i+1}: {elapsed:.0f} ms")
        
        self.results["tests"]["optimization_small"] = self._calculate_stats(times, iterations)
        print(f"  Mean: {self.results['tests']['optimization_small']['mean_ms']:.2f} ms")
        
    async def benchmark_optimization_large(self, iterations: int = 10):
        """Benchmark optimization with all 6 zones"""
        print("\n5. Large Optimization Test (6 zones, full features)")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/optimize"
        data = {
            "zone_requests": [
                {
                    "zone_id": f"zone_{i}",
                    "required_volume": 50000 - i * 5000,
                    "required_flow_rate": 20.0 - i * 2,
                    "priority": 1 if i <= 2 else 2 if i <= 4 else 3
                }
                for i in range(1, 7)
            ],
            "source_water_level": 222.0,
            "objective": "BALANCED",
            "include_contingency": True,
            "include_energy_recovery": True
        }
        times = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(iterations):
                start = time.time()
                response = await client.post(url, json=data)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                print(f"  Iteration {i+1}: {elapsed:.0f} ms")
        
        self.results["tests"]["optimization_large"] = self._calculate_stats(times, iterations)
        print(f"  Mean: {self.results['tests']['optimization_large']['mean_ms']:.2f} ms")
        
    async def benchmark_concurrent_requests(self, concurrent: int = 10, total: int = 100):
        """Benchmark concurrent request handling"""
        print(f"\n6. Concurrent Requests Test ({concurrent} concurrent)")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/feasibility/zone_2"
        params = {"required_flow": 10.0}
        
        async def make_request(client: httpx.AsyncClient, request_id: int):
            start = time.time()
            response = await client.get(url, params=params)
            elapsed = (time.time() - start) * 1000
            return elapsed, response.status_code
        
        async with httpx.AsyncClient() as client:
            start_total = time.time()
            
            # Create batches
            times = []
            errors = 0
            
            for batch_start in range(0, total, concurrent):
                batch_end = min(batch_start + concurrent, total)
                batch_size = batch_end - batch_start
                
                # Run batch concurrently
                tasks = [make_request(client, i) for i in range(batch_size)]
                results = await asyncio.gather(*tasks)
                
                for elapsed, status in results:
                    times.append(elapsed)
                    if status != 200:
                        errors += 1
                
                print(f"  Progress: {batch_end}/{total}")
            
            total_time = (time.time() - start_total) * 1000
        
        self.results["tests"]["concurrent_requests"] = {
            "concurrent": concurrent,
            "total_requests": total,
            "total_time_ms": total_time,
            "requests_per_second": total / (total_time / 1000),
            "errors": errors,
            **self._calculate_stats(times, total)
        }
        
        print(f"  RPS: {self.results['tests']['concurrent_requests']['requests_per_second']:.1f}")
        print(f"  Mean: {self.results['tests']['concurrent_requests']['mean_ms']:.2f} ms")
        
    async def benchmark_flow_split(self, iterations: int = 20):
        """Benchmark flow split optimization"""
        print("\n7. Flow Split Optimization Test")
        print("-" * 30)
        
        url = f"{BASE_URL}{API_PREFIX}/flow-split/optimize"
        data = {
            "total_inflow": 100.0,
            "zone_requests": [
                {"zone_id": f"zone_{i}", "required_flow_rate": 15.0 + i, "priority": 1}
                for i in range(1, 5)
            ],
            "objective": "MAXIMIZE_EFFICIENCY"
        }
        times = []
        
        async with httpx.AsyncClient() as client:
            for i in range(iterations):
                start = time.time()
                response = await client.post(url, json=data)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                
                if i % 5 == 0:
                    print(f"  Progress: {i}/{iterations}")
        
        self.results["tests"]["flow_split"] = self._calculate_stats(times, iterations)
        print(f"  Mean: {self.results['tests']['flow_split']['mean_ms']:.2f} ms")
        
    async def benchmark_large_scale(self):
        """Simulate large scale operation"""
        print("\n8. Large Scale Simulation")
        print("-" * 30)
        
        # Simulate a day of operations
        operations = [
            ("Morning optimization", "MINIMIZE_TRAVEL_TIME", 6),
            ("Noon adjustment", "BALANCED", 4),
            ("Evening optimization", "MAXIMIZE_EFFICIENCY", 5)
        ]
        
        total_start = time.time()
        operation_times = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for op_name, objective, zone_count in operations:
                print(f"\n  {op_name} ({zone_count} zones)...")
                
                # Full optimization
                url = f"{BASE_URL}{API_PREFIX}/optimize"
                data = {
                    "zone_requests": [
                        {
                            "zone_id": f"zone_{i}",
                            "required_volume": 30000,
                            "required_flow_rate": 12.0,
                            "priority": 1 if i <= 3 else 2
                        }
                        for i in range(1, zone_count + 1)
                    ],
                    "source_water_level": 221.5,
                    "objective": objective
                }
                
                op_start = time.time()
                
                # Optimization
                response = await client.post(url, json=data)
                opt_time = (time.time() - op_start) * 1000
                
                # Feasibility checks
                for i in range(1, zone_count + 1):
                    await client.get(
                        f"{BASE_URL}{API_PREFIX}/feasibility/zone_{i}",
                        params={"required_flow": 12.0}
                    )
                
                # Flow monitoring
                await client.post(
                    f"{BASE_URL}{API_PREFIX}/flow-split/optimize",
                    json={
                        "total_inflow": 80.0,
                        "zone_requests": data["zone_requests"][:3]
                    }
                )
                
                op_time = (time.time() - op_start) * 1000
                operation_times.append(op_time)
                print(f"    Completed in {op_time:.0f} ms")
        
        total_time = (time.time() - total_start) * 1000
        
        self.results["tests"]["large_scale"] = {
            "operations": len(operations),
            "total_time_ms": total_time,
            "operation_times_ms": operation_times,
            "mean_operation_ms": statistics.mean(operation_times)
        }
        
        print(f"\n  Total simulation time: {total_time/1000:.1f} seconds")
        
    def _calculate_stats(self, times: List[float], count: int) -> Dict:
        """Calculate statistics from timing data"""
        sorted_times = sorted(times)
        return {
            "iterations": count,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "p95_ms": sorted_times[int(0.95 * len(times))],
            "p99_ms": sorted_times[int(0.99 * len(times))]
        }
        
    def generate_report(self):
        """Generate performance report"""
        print("\n" + "=" * 50)
        print("PERFORMANCE BENCHMARK REPORT")
        print("=" * 50)
        
        # Summary table
        print("\nEndpoint Performance Summary:")
        print("-" * 70)
        print(f"{'Test':<35} {'Mean (ms)':<12} {'P95 (ms)':<12} {'P99 (ms)':<12}")
        print("-" * 70)
        
        for test_name, results in self.results["tests"].items():
            if "mean_ms" in results:
                print(f"{test_name:<35} {results['mean_ms']:<12.2f} "
                      f"{results.get('p95_ms', 0):<12.2f} "
                      f"{results.get('p99_ms', 0):<12.2f}")
        
        # Concurrent performance
        if "concurrent_requests" in self.results["tests"]:
            cr = self.results["tests"]["concurrent_requests"]
            print(f"\nConcurrent Performance:")
            print(f"  Requests per second: {cr['requests_per_second']:.1f}")
            print(f"  Error rate: {cr['errors']/cr['total_requests']*100:.1f}%")
        
        # Large scale results
        if "large_scale" in self.results["tests"]:
            ls = self.results["tests"]["large_scale"]
            print(f"\nLarge Scale Simulation:")
            print(f"  Total time: {ls['total_time_ms']/1000:.1f} seconds")
            print(f"  Mean operation time: {ls['mean_operation_ms']:.0f} ms")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nDetailed results saved to: {filename}")
        
        # Performance recommendations
        print("\nPerformance Analysis:")
        print("-" * 50)
        
        health_mean = self.results["tests"]["health_check"]["mean_ms"]
        if health_mean < 10:
            print("✓ Health check latency: Excellent")
        elif health_mean < 50:
            print("✓ Health check latency: Good")
        else:
            print("⚠ Health check latency: Needs optimization")
        
        if "optimization_large" in self.results["tests"]:
            opt_mean = self.results["tests"]["optimization_large"]["mean_ms"]
            if opt_mean < 500:
                print("✓ Full optimization: Excellent performance")
            elif opt_mean < 1000:
                print("✓ Full optimization: Acceptable performance")
            else:
                print("⚠ Full optimization: Consider optimization")
        
        if "concurrent_requests" in self.results["tests"]:
            rps = self.results["tests"]["concurrent_requests"]["requests_per_second"]
            if rps > 100:
                print("✓ Concurrent handling: Excellent")
            elif rps > 50:
                print("✓ Concurrent handling: Good")
            else:
                print("⚠ Concurrent handling: May need scaling")


async def main():
    """Run benchmark suite"""
    benchmark = PerformanceBenchmark()
    
    try:
        # Check if service is running
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                print(f"Error: Service not responding at {BASE_URL}")
                return
    except Exception as e:
        print(f"Error: Cannot connect to service at {BASE_URL}")
        print(f"Details: {e}")
        return
    
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())