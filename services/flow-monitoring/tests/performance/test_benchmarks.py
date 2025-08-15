"""
Performance benchmarks for Flow Monitoring Service
Tests system performance under various load conditions
"""

import pytest
import asyncio
import time
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

from core.enhanced_hydraulic_solver import EnhancedHydraulicSolver, SolverSettings
from core.gate_registry import GateRegistry
from core.calibrated_gate_hydraulics import CalibratedGateHydraulics, HydraulicConditions


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    @pytest.fixture
    def large_network_config(self):
        """Create a large network for performance testing"""
        nodes = {}
        gates = {}
        canals = {}
        
        # Create 50 nodes
        for i in range(50):
            nodes[f"Node_{i}"] = {
                "type": "junction" if i > 0 else "reservoir",
                "elevation_m": 100.0 - i * 0.5,
                "min_depth_m": 0.5,
                "max_depth_m": 5.0,
                "demand_m3s": 0.5 if i % 5 == 0 else 0.0
            }
        
        # Create 49 gates connecting nodes
        for i in range(49):
            gates[f"Gate_{i}"] = {
                "upstream": f"Node_{i}",
                "downstream": f"Node_{i+1}",
                "type": "slide",
                "width_m": 3.0,
                "height_m": 2.5,
                "sill_elevation_m": 95.0 - i * 0.5
            }
        
        # Create 49 canal sections
        for i in range(49):
            canals[f"Canal_{i}"] = {
                "upstream": f"Node_{i}",
                "downstream": f"Node_{i+1}",
                "length_m": 1000.0,
                "bottom_width_m": 8.0,
                "side_slope": 1.5,
                "manning_n": 0.025,
                "bed_slope": 0.0001
            }
        
        return {"nodes": nodes, "gates": gates, "canals": canals}
    
    def test_hydraulic_solver_performance(self, large_network_config, benchmark):
        """Benchmark hydraulic solver with large network"""
        registry = GateRegistry()
        solver = EnhancedHydraulicSolver(large_network_config, registry)
        
        # Set up test conditions
        gate_openings = {f"Gate_{i}": 1.5 for i in range(49)}
        demands = {f"Node_{i}": 0.5 for i in range(0, 50, 5)}
        
        # Benchmark solving
        def solve_network():
            return solver.solve_steady_state(gate_openings, demands)
        
        result = benchmark(solve_network)
        
        assert result.convergence_achieved is True
        assert result.iterations < 100
        
        # Performance assertions
        benchmark.extra_info['iterations'] = result.iterations
        benchmark.extra_info['nodes'] = len(solver.nodes)
        benchmark.extra_info['gates'] = len(solver.gates)
    
    def test_concurrent_gate_calculations(self, calibrated_hydraulics, benchmark):
        """Benchmark concurrent gate flow calculations"""
        # Create conditions for multiple gates
        conditions = {}
        for i in range(100):
            conditions[f"Gate_{i}"] = HydraulicConditions(
                upstream_level_m=100.0 + np.random.uniform(-5, 5),
                downstream_level_m=95.0 + np.random.uniform(-5, 5),
                gate_opening_m=np.random.uniform(0.5, 3.0),
                temperature_c=25.0
            )
        
        # Add gate properties for test gates
        for i in range(100):
            if f"Gate_{i}" not in calibrated_hydraulics.gate_properties:
                calibrated_hydraulics.gate_properties[f"Gate_{i}"] = Mock()
        
        def calculate_all_flows():
            return calibrated_hydraulics.calculate_batch_flows(conditions)
        
        results = benchmark(calculate_all_flows)
        
        assert len(results) == 100
        benchmark.extra_info['gates_calculated'] = len(results)
    
    @pytest.mark.asyncio
    async def test_api_throughput(self, test_client):
        """Benchmark API request throughput"""
        client = test_client
        
        async def make_request():
            response = await client.get("/api/v1/gates/state")
            return response.status_code == 200
        
        # Measure throughput
        start_time = time.time()
        tasks = []
        
        for _ in range(100):
            tasks.append(asyncio.create_task(make_request()))
        
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        successful = sum(results)
        throughput = successful / duration
        
        assert successful >= 95  # At least 95% success rate
        assert throughput > 50  # At least 50 requests per second
        
        print(f"API Throughput: {throughput:.2f} requests/second")
    
    def test_memory_usage_under_load(self, large_network_config):
        """Test memory usage with large network"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create multiple solver instances
        solvers = []
        for _ in range(10):
            registry = GateRegistry()
            solver = EnhancedHydraulicSolver(large_network_config, registry)
            solvers.append(solver)
        
        # Perform calculations
        for solver in solvers:
            gate_openings = {f"Gate_{i}": 1.5 for i in range(49)}
            demands = {f"Node_{i}": 0.5 for i in range(0, 50, 5)}
            solver.solve_steady_state(gate_openings, demands)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory increase: {memory_increase:.2f} MB")
        assert memory_increase < 500  # Should not exceed 500MB
    
    def test_solver_convergence_speed(self, mock_network_config, benchmark):
        """Benchmark solver convergence speed with different settings"""
        registry = GateRegistry()
        
        # Test different solver settings
        settings_variants = [
            SolverSettings(relaxation_factor=0.5),
            SolverSettings(relaxation_factor=0.7),
            SolverSettings(relaxation_factor=0.9),
            SolverSettings(use_adaptive_relaxation=True)
        ]
        
        results = []
        for settings in settings_variants:
            solver = EnhancedHydraulicSolver(
                mock_network_config, registry, settings
            )
            
            gate_openings = {"G_RES_J1": 2.0, "G_J1_Z1": 1.5}
            demands = {"Zone_1": 2.5, "Zone_2": 3.0}
            
            start = time.time()
            state = solver.solve_steady_state(gate_openings, demands)
            duration = time.time() - start
            
            results.append({
                'relaxation': settings.relaxation_factor,
                'adaptive': settings.use_adaptive_relaxation,
                'iterations': state.iterations,
                'time': duration,
                'converged': state.convergence_achieved
            })
        
        # Adaptive should generally perform better
        adaptive_result = next(r for r in results if r['adaptive'])
        assert adaptive_result['converged'] is True
        
        for result in results:
            print(f"Relaxation: {result['relaxation']}, "
                  f"Iterations: {result['iterations']}, "
                  f"Time: {result['time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_mode_transitions(self, integrated_system):
        """Test performance of concurrent mode transitions"""
        controller = integrated_system
        
        # Add many gates
        gate_ids = [f"Gate_{i}" for i in range(20)]
        for gate_id in gate_ids:
            controller.gate_registry.add_automated_gate(Mock(
                gate_id=gate_id,
                control_mode=ControlMode.AUTO
            ))
        
        # Measure concurrent transitions
        start_time = time.time()
        
        tasks = []
        for i, gate_id in enumerate(gate_ids):
            target_mode = ControlMode.MANUAL if i % 2 == 0 else ControlMode.MAINTENANCE
            task = controller.execute_mode_transition(
                gate_id, target_mode, "Concurrent test"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start_time
        
        successful = sum(1 for r in results if r is True)
        
        assert successful >= 18  # At least 90% success
        assert duration < 5.0  # Should complete within 5 seconds
        
        print(f"Concurrent transitions: {successful}/{len(gate_ids)} in {duration:.2f}s")
    
    def test_state_preservation_performance(self, mock_db_manager, benchmark):
        """Benchmark state preservation operations"""
        from core.state_preservation import StatePreservationSystem
        
        preservation = StatePreservationSystem(mock_db_manager, None)
        
        # Create a complex state
        state = {
            "timestamp": datetime.now(),
            "gates": {f"Gate_{i}": {
                "mode": "auto",
                "opening": np.random.uniform(0, 3),
                "flow": np.random.uniform(0, 10)
            } for i in range(50)},
            "water_levels": {f"Node_{i}": np.random.uniform(90, 110) 
                           for i in range(50)},
            "active_deliveries": [
                {"node": f"Node_{i}", "flow": 2.5, "duration": 4}
                for i in range(10)
            ]
        }
        
        def preserve_state():
            preservation.preserve_state(
                TransitionType.NORMAL_TO_EMERGENCY,
                "Performance test",
                state,
                "test_user"
            )
        
        benchmark(preserve_state)
        
        benchmark.extra_info['state_size_kb'] = len(str(state)) / 1024
    
    def test_gradual_transition_performance(self, integrated_system, benchmark):
        """Benchmark gradual transition calculations"""
        controller = integrated_system
        
        # Create transition plans for multiple gates
        plans = []
        for i in range(10):
            plan = controller.transition_controller.create_transition_plan(
                gate_id=f"Gate_{i}",
                current_opening=2.0,
                target_opening=1.0,
                strategy=TransitionStrategy.S_CURVE,
                duration_s=300
            )
            plans.append(plan)
        
        def execute_all_transitions():
            results = []
            for plan in plans:
                result = controller.transition_controller.calculate_transition_steps(plan)
                results.append(result)
            return results
        
        results = benchmark(execute_all_transitions)
        
        assert len(results) == 10
        benchmark.extra_info['total_steps'] = sum(len(r.steps) for r in results)
    
    def test_mass_balance_calculation_performance(self, large_network_config, benchmark):
        """Benchmark mass balance calculations for large network"""
        registry = GateRegistry()
        solver = EnhancedHydraulicSolver(large_network_config, registry)
        
        # Set up a complex flow state
        solver.current_state.gate_flows = {
            f"Gate_{i}": np.random.uniform(1, 10) for i in range(49)
        }
        
        def calculate_all_mass_balances():
            errors = []
            for node_id in solver.nodes:
                inflow, outflow = solver._calculate_node_flows(node_id)
                error = abs(inflow - outflow)
                errors.append(error)
            return errors
        
        errors = benchmark(calculate_all_mass_balances)
        
        assert len(errors) == 50
        benchmark.extra_info['max_error'] = max(errors)
        benchmark.extra_info['avg_error'] = np.mean(errors)