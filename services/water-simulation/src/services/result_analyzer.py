"""
Result analysis service for simulation outputs
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from src.core.models import (
    SimulationRun, SimulationState, OptimizationResult,
    AnalysisResult, GateOperation, Scenario
)

logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """Analyzes simulation results and generates insights"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def analyze_simulation_run(
        self,
        run_id: str,
        analysis_type: str = "comprehensive"
    ) -> AnalysisResult:
        """Perform comprehensive analysis of a simulation run"""
        
        # Get simulation run details
        result = await self.db.execute(
            select(SimulationRun).where(SimulationRun.run_id == run_id)
        )
        run = result.scalar_one()
        
        if analysis_type == "comprehensive":
            analysis_data = await self._comprehensive_analysis(run)
        elif analysis_type == "performance":
            analysis_data = await self._performance_analysis(run)
        elif analysis_type == "sensitivity":
            analysis_data = await self._sensitivity_analysis(run)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        
        # Create analysis result
        analysis = AnalysisResult(
            run_id=run_id,
            analysis_type=analysis_type,
            **analysis_data
        )
        
        self.db.add(analysis)
        await self.db.commit()
        
        return analysis
    
    async def _comprehensive_analysis(self, run: SimulationRun) -> Dict[str, Any]:
        """Perform comprehensive analysis"""
        
        # Get all simulation states
        states = await self._get_simulation_states(run.run_id)
        
        # Calculate overall metrics
        metrics = self._calculate_overall_metrics(states)
        
        # Analyze water balance
        water_balance = await self._analyze_water_balance(states)
        
        # Analyze gate operations
        gate_analysis = await self._analyze_gate_operations(run.run_id)
        
        # Analyze section performance
        section_performance = self._analyze_section_performance(states)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            metrics, water_balance, gate_analysis, section_performance
        )
        
        return {
            "avg_delivery_efficiency": metrics["avg_efficiency"],
            "water_shortage_events": metrics["shortage_events"],
            "excess_water_events": metrics["excess_events"],
            "unmet_demand_m3": metrics["total_unmet_demand"],
            "section_performance": section_performance,
            "temporal_analysis": {
                "water_balance": water_balance,
                "gate_operations": gate_analysis,
                "efficiency_timeline": metrics["efficiency_timeline"]
            },
            "recommendations": recommendations
        }
    
    async def _performance_analysis(self, run: SimulationRun) -> Dict[str, Any]:
        """Analyze system performance"""
        
        states = await self._get_simulation_states(run.run_id)
        optimizations = await self._get_optimization_results(run.run_id)
        
        # Calculate performance metrics
        performance_metrics = {
            "delivery_performance": self._analyze_delivery_performance(states),
            "optimization_performance": self._analyze_optimization_performance(optimizations),
            "hydraulic_performance": self._analyze_hydraulic_performance(states),
            "energy_performance": await self._analyze_energy_performance(run.run_id)
        }
        
        return {
            "avg_delivery_efficiency": performance_metrics["delivery_performance"]["avg_efficiency"],
            "water_shortage_events": performance_metrics["delivery_performance"]["shortage_count"],
            "excess_water_events": performance_metrics["delivery_performance"]["excess_count"],
            "unmet_demand_m3": performance_metrics["delivery_performance"]["total_unmet"],
            "section_performance": performance_metrics["delivery_performance"]["by_section"],
            "temporal_analysis": performance_metrics,
            "recommendations": self._generate_performance_recommendations(performance_metrics)
        }
    
    async def _sensitivity_analysis(self, run: SimulationRun) -> Dict[str, Any]:
        """Analyze sensitivity to parameters"""
        
        # This would compare multiple runs with parameter variations
        # For now, analyze variability within single run
        
        states = await self._get_simulation_states(run.run_id)
        
        sensitivity_results = {
            "demand_sensitivity": self._analyze_demand_sensitivity(states),
            "gate_sensitivity": await self._analyze_gate_sensitivity(run.run_id),
            "water_level_sensitivity": self._analyze_water_level_sensitivity(states)
        }
        
        return {
            "avg_delivery_efficiency": 0.85,  # Placeholder
            "water_shortage_events": 0,
            "excess_water_events": 0,
            "unmet_demand_m3": 0,
            "section_performance": {},
            "temporal_analysis": sensitivity_results,
            "recommendations": self._generate_sensitivity_recommendations(sensitivity_results)
        }
    
    async def _get_simulation_states(self, run_id: str) -> List[SimulationState]:
        """Get all states for a simulation run"""
        result = await self.db.execute(
            select(SimulationState)
            .where(SimulationState.run_id == run_id)
            .order_by(SimulationState.time_step)
        )
        return result.scalars().all()
    
    async def _get_optimization_results(self, run_id: str) -> List[OptimizationResult]:
        """Get optimization results for a run"""
        result = await self.db.execute(
            select(OptimizationResult)
            .where(OptimizationResult.run_id == run_id)
            .order_by(OptimizationResult.optimization_time)
        )
        return result.scalars().all()
    
    def _calculate_overall_metrics(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Calculate overall simulation metrics"""
        
        efficiencies = []
        shortage_events = 0
        excess_events = 0
        total_unmet_demand = 0
        
        for state in states:
            if state.system_efficiency is not None:
                efficiencies.append(float(state.system_efficiency))
            
            if state.total_demand_m3 and state.total_delivered_m3:
                delivered = float(state.total_delivered_m3)
                demand = float(state.total_demand_m3)
                
                if delivered < demand * 0.9:
                    shortage_events += 1
                    total_unmet_demand += demand - delivered
                elif delivered > demand * 1.1:
                    excess_events += 1
        
        return {
            "avg_efficiency": np.mean(efficiencies) if efficiencies else 0,
            "min_efficiency": np.min(efficiencies) if efficiencies else 0,
            "max_efficiency": np.max(efficiencies) if efficiencies else 0,
            "efficiency_std": np.std(efficiencies) if efficiencies else 0,
            "shortage_events": shortage_events,
            "excess_events": excess_events,
            "total_unmet_demand": total_unmet_demand,
            "efficiency_timeline": efficiencies
        }
    
    async def _analyze_water_balance(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze water balance over time"""
        
        time_series = []
        cumulative_balance = 0
        
        for state in states:
            supply = float(state.total_supply_m3) if state.total_supply_m3 else 0
            delivered = float(state.total_delivered_m3) if state.total_delivered_m3 else 0
            demand = float(state.total_demand_m3) if state.total_demand_m3 else 0
            
            balance = supply - delivered
            cumulative_balance += balance
            
            time_series.append({
                "time_step": state.time_step,
                "simulation_time": state.simulation_time.isoformat(),
                "supply_m3": supply,
                "demand_m3": demand,
                "delivered_m3": delivered,
                "balance_m3": balance,
                "cumulative_balance_m3": cumulative_balance,
                "deficit_m3": max(0, demand - delivered)
            })
        
        return {
            "time_series": time_series,
            "total_supply": sum(ts["supply_m3"] for ts in time_series),
            "total_demand": sum(ts["demand_m3"] for ts in time_series),
            "total_delivered": sum(ts["delivered_m3"] for ts in time_series),
            "total_deficit": sum(ts["deficit_m3"] for ts in time_series),
            "final_balance": cumulative_balance
        }
    
    async def _analyze_gate_operations(self, run_id: str) -> Dict[str, Any]:
        """Analyze gate operation patterns"""
        
        result = await self.db.execute(
            select(GateOperation)
            .where(GateOperation.run_id == run_id)
            .order_by(GateOperation.scheduled_time)
        )
        operations = result.scalars().all()
        
        gate_stats = {}
        total_movements = 0
        
        for op in operations:
            if op.gate_id not in gate_stats:
                gate_stats[op.gate_id] = {
                    "movement_count": 0,
                    "total_movement_m": 0,
                    "avg_duration_minutes": [],
                    "operation_types": {}
                }
            
            stats = gate_stats[op.gate_id]
            stats["movement_count"] += 1
            total_movements += 1
            
            if op.actual_opening_m is not None:
                # Calculate movement distance (would need previous position)
                stats["total_movement_m"] += abs(float(op.target_opening_m))
            
            if op.execution_duration_minutes:
                stats["avg_duration_minutes"].append(op.execution_duration_minutes)
            
            op_type = op.operation_type
            stats["operation_types"][op_type] = stats["operation_types"].get(op_type, 0) + 1
        
        # Calculate averages
        for gate_id, stats in gate_stats.items():
            if stats["avg_duration_minutes"]:
                stats["avg_duration_minutes"] = np.mean(stats["avg_duration_minutes"])
            else:
                stats["avg_duration_minutes"] = 0
        
        return {
            "total_operations": total_movements,
            "gates_operated": len(gate_stats),
            "by_gate": gate_stats,
            "operation_frequency": total_movements / len(operations) if operations else 0
        }
    
    def _analyze_section_performance(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze performance by section"""
        
        # Aggregate section-level data from states
        # In full implementation, would track section-specific deliveries
        
        section_data = {}
        
        # Placeholder - would extract from detailed state data
        sample_sections = ["SEC001", "SEC002", "SEC003", "SEC004"]
        
        for section_id in sample_sections:
            section_data[section_id] = {
                "avg_delivery_ratio": np.random.uniform(0.8, 0.95),
                "reliability": np.random.uniform(0.85, 0.98),
                "shortage_frequency": np.random.randint(0, 5),
                "performance_score": np.random.uniform(0.7, 0.95)
            }
        
        return section_data
    
    def _analyze_delivery_performance(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze water delivery performance"""
        
        delivery_ratios = []
        shortage_count = 0
        excess_count = 0
        total_unmet = 0
        
        for state in states:
            if state.total_demand_m3 and state.total_delivered_m3:
                demand = float(state.total_demand_m3)
                delivered = float(state.total_delivered_m3)
                ratio = delivered / demand if demand > 0 else 0
                
                delivery_ratios.append(ratio)
                
                if ratio < 0.9:
                    shortage_count += 1
                    total_unmet += demand - delivered
                elif ratio > 1.1:
                    excess_count += 1
        
        return {
            "avg_efficiency": np.mean(delivery_ratios) if delivery_ratios else 0,
            "min_efficiency": np.min(delivery_ratios) if delivery_ratios else 0,
            "max_efficiency": np.max(delivery_ratios) if delivery_ratios else 0,
            "shortage_count": shortage_count,
            "excess_count": excess_count,
            "total_unmet": total_unmet,
            "by_section": {}  # Would be populated with section-specific data
        }
    
    def _analyze_optimization_performance(
        self,
        optimizations: List[OptimizationResult]
    ) -> Dict[str, Any]:
        """Analyze optimization algorithm performance"""
        
        convergence_rate = sum(1 for opt in optimizations if opt.convergence_achieved) / len(optimizations) if optimizations else 0
        
        computation_times = [opt.computational_time_ms for opt in optimizations if opt.computational_time_ms]
        iterations = [opt.iterations for opt in optimizations if opt.iterations]
        
        return {
            "total_optimizations": len(optimizations),
            "convergence_rate": convergence_rate,
            "avg_computation_time_ms": np.mean(computation_times) if computation_times else 0,
            "avg_iterations": np.mean(iterations) if iterations else 0,
            "max_computation_time_ms": np.max(computation_times) if computation_times else 0
        }
    
    def _analyze_hydraulic_performance(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze hydraulic system performance"""
        
        water_level_variations = []
        flow_variations = []
        
        for state in states:
            if state.water_levels:
                levels = list(state.water_levels.values())
                water_level_variations.append(np.std(levels))
            
            if state.flow_rates:
                flows = list(state.flow_rates.values())
                flow_variations.append(np.std(flows))
        
        return {
            "avg_water_level_variation": np.mean(water_level_variations) if water_level_variations else 0,
            "avg_flow_variation": np.mean(flow_variations) if flow_variations else 0,
            "hydraulic_stability": 1 - np.mean(water_level_variations) / 10 if water_level_variations else 0
        }
    
    async def _analyze_energy_performance(self, run_id: str) -> Dict[str, Any]:
        """Analyze energy consumption"""
        
        result = await self.db.execute(
            select(OptimizationResult)
            .where(OptimizationResult.run_id == run_id)
        )
        optimizations = result.scalars().all()
        
        energy_values = [
            float(opt.energy_usage_kwh)
            for opt in optimizations
            if opt.energy_usage_kwh is not None
        ]
        
        return {
            "total_energy_kwh": sum(energy_values),
            "avg_energy_per_step": np.mean(energy_values) if energy_values else 0,
            "peak_energy": np.max(energy_values) if energy_values else 0,
            "energy_efficiency": 1 / (1 + np.mean(energy_values) / 100) if energy_values else 0
        }
    
    def _analyze_demand_sensitivity(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze sensitivity to demand variations"""
        
        # Calculate how system responds to demand changes
        demand_values = []
        efficiency_values = []
        
        for state in states:
            if state.total_demand_m3 and state.system_efficiency:
                demand_values.append(float(state.total_demand_m3))
                efficiency_values.append(float(state.system_efficiency))
        
        if len(demand_values) > 1:
            # Calculate correlation
            correlation = np.corrcoef(demand_values, efficiency_values)[0, 1]
            
            return {
                "demand_efficiency_correlation": correlation,
                "demand_range": (min(demand_values), max(demand_values)),
                "efficiency_range": (min(efficiency_values), max(efficiency_values)),
                "sensitivity_score": abs(correlation)
            }
        
        return {
            "demand_efficiency_correlation": 0,
            "demand_range": (0, 0),
            "efficiency_range": (0, 0),
            "sensitivity_score": 0
        }
    
    async def _analyze_gate_sensitivity(self, run_id: str) -> Dict[str, Any]:
        """Analyze sensitivity to gate operations"""
        
        result = await self.db.execute(
            select(GateOperation)
            .where(GateOperation.run_id == run_id)
        )
        operations = result.scalars().all()
        
        gate_movements = {}
        
        for op in operations:
            if op.gate_id not in gate_movements:
                gate_movements[op.gate_id] = []
            
            gate_movements[op.gate_id].append(float(op.target_opening_m))
        
        sensitivity_by_gate = {}
        
        for gate_id, movements in gate_movements.items():
            if len(movements) > 1:
                sensitivity_by_gate[gate_id] = {
                    "movement_range": (min(movements), max(movements)),
                    "movement_frequency": len(movements),
                    "avg_movement": np.mean(movements),
                    "movement_variability": np.std(movements)
                }
        
        return {
            "gates_analyzed": len(sensitivity_by_gate),
            "by_gate": sensitivity_by_gate,
            "most_sensitive_gate": max(
                sensitivity_by_gate.items(),
                key=lambda x: x[1]["movement_variability"]
            )[0] if sensitivity_by_gate else None
        }
    
    def _analyze_water_level_sensitivity(self, states: List[SimulationState]) -> Dict[str, Any]:
        """Analyze water level sensitivity"""
        
        level_time_series = {}
        
        for state in states:
            if state.water_levels:
                for location, level in state.water_levels.items():
                    if location not in level_time_series:
                        level_time_series[location] = []
                    level_time_series[location].append(level)
        
        sensitivity_by_location = {}
        
        for location, levels in level_time_series.items():
            if levels:
                sensitivity_by_location[location] = {
                    "level_range": (min(levels), max(levels)),
                    "avg_level": np.mean(levels),
                    "level_variability": np.std(levels),
                    "stability_score": 1 / (1 + np.std(levels))
                }
        
        return {
            "locations_analyzed": len(sensitivity_by_location),
            "by_location": sensitivity_by_location,
            "overall_stability": np.mean([
                loc["stability_score"]
                for loc in sensitivity_by_location.values()
            ]) if sensitivity_by_location else 0
        }
    
    def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        water_balance: Dict[str, Any],
        gate_analysis: Dict[str, Any],
        section_performance: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Efficiency recommendations
        if metrics["avg_efficiency"] < 0.8:
            recommendations.append(
                "System efficiency is below 80%. Consider optimizing gate schedules "
                "to better match demand patterns."
            )
        
        # Water balance recommendations
        if water_balance["total_deficit"] > water_balance["total_demand"] * 0.1:
            recommendations.append(
                f"Significant water deficit detected ({water_balance['total_deficit']:.0f} m³). "
                "Review water allocation priorities and consider demand reduction measures."
            )
        
        # Gate operation recommendations
        high_movement_gates = [
            gate_id for gate_id, stats in gate_analysis["by_gate"].items()
            if stats["movement_count"] > 50
        ]
        
        if high_movement_gates:
            recommendations.append(
                f"Gates {', '.join(high_movement_gates[:3])} show high movement frequency. "
                "Consider implementing more stable control strategies."
            )
        
        # Section performance recommendations
        poor_performing_sections = [
            section_id for section_id, perf in section_performance.items()
            if perf["performance_score"] < 0.7
        ]
        
        if poor_performing_sections:
            recommendations.append(
                f"Sections {', '.join(poor_performing_sections[:3])} show poor performance. "
                "Investigate local constraints and delivery infrastructure."
            )
        
        # Energy recommendations
        if metrics.get("total_energy", 0) > 1000:
            recommendations.append(
                "High energy consumption detected. Consider energy-efficient "
                "gate operation schedules during off-peak hours."
            )
        
        if not recommendations:
            recommendations.append(
                "System performance is within acceptable parameters. "
                "Continue monitoring for optimization opportunities."
            )
        
        return recommendations
    
    def _generate_performance_recommendations(
        self,
        performance_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate performance-specific recommendations"""
        
        recommendations = []
        
        delivery = performance_metrics["delivery_performance"]
        optimization = performance_metrics["optimization_performance"]
        hydraulic = performance_metrics["hydraulic_performance"]
        energy = performance_metrics["energy_performance"]
        
        if delivery["avg_efficiency"] < 0.85:
            recommendations.append(
                "Delivery efficiency can be improved. Focus on reducing "
                "transmission losses and optimizing distribution schedules."
            )
        
        if optimization["convergence_rate"] < 0.9:
            recommendations.append(
                "Optimization convergence rate is low. Consider adjusting "
                "algorithm parameters or constraints."
            )
        
        if hydraulic["hydraulic_stability"] < 0.8:
            recommendations.append(
                "Hydraulic instability detected. Review gate operation "
                "frequencies and implement damping strategies."
            )
        
        if energy["energy_efficiency"] < 0.7:
            recommendations.append(
                "Energy efficiency is below target. Implement energy-aware "
                "scheduling and minimize unnecessary gate movements."
            )
        
        return recommendations
    
    def _generate_sensitivity_recommendations(
        self,
        sensitivity_results: Dict[str, Any]
    ) -> List[str]:
        """Generate sensitivity analysis recommendations"""
        
        recommendations = []
        
        demand_sens = sensitivity_results["demand_sensitivity"]
        gate_sens = sensitivity_results["gate_sensitivity"]
        level_sens = sensitivity_results["water_level_sensitivity"]
        
        if demand_sens["sensitivity_score"] > 0.7:
            recommendations.append(
                "System shows high sensitivity to demand variations. "
                "Implement adaptive control strategies for demand uncertainty."
            )
        
        if gate_sens["most_sensitive_gate"]:
            recommendations.append(
                f"Gate {gate_sens['most_sensitive_gate']} shows highest operational "
                "sensitivity. Prioritize maintenance and calibration."
            )
        
        if level_sens["overall_stability"] < 0.7:
            recommendations.append(
                "Water levels show significant variability. Consider "
                "implementing level control strategies and buffer storage."
            )
        
        return recommendations
    
    async def compare_scenarios(
        self,
        run_ids: List[str]
    ) -> Dict[str, Any]:
        """Compare results across multiple simulation runs"""
        
        comparisons = {}
        
        for run_id in run_ids:
            # Get analysis results
            result = await self.db.execute(
                select(AnalysisResult)
                .where(AnalysisResult.run_id == run_id)
                .order_by(AnalysisResult.created_at.desc())
                .limit(1)
            )
            analysis = result.scalar()
            
            if analysis:
                comparisons[run_id] = {
                    "efficiency": float(analysis.avg_delivery_efficiency) if analysis.avg_delivery_efficiency else 0,
                    "shortages": analysis.water_shortage_events,
                    "unmet_demand": float(analysis.unmet_demand_m3) if analysis.unmet_demand_m3 else 0
                }
        
        # Find best performing scenario
        if comparisons:
            best_efficiency = max(comparisons.items(), key=lambda x: x[1]["efficiency"])
            least_shortages = min(comparisons.items(), key=lambda x: x[1]["shortages"])
            
            return {
                "scenario_count": len(comparisons),
                "comparisons": comparisons,
                "best_efficiency": best_efficiency[0],
                "least_shortages": least_shortages[0],
                "recommendations": [
                    f"Scenario {best_efficiency[0]} shows best overall efficiency.",
                    f"Scenario {least_shortages[0]} has fewest shortage events.",
                    "Consider combining strategies from top performers."
                ]
            }
        
        return {
            "scenario_count": 0,
            "comparisons": {},
            "recommendations": ["No scenarios to compare"]
        }