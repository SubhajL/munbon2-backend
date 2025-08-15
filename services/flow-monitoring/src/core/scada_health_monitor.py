#!/usr/bin/env python3
"""
SCADA Health Monitoring and Availability Checker
Monitors SCADA system health, communication status, and data freshness
"""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import aiohttp
import json
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Overall health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Types of health checks"""
    CONNECTIVITY = "connectivity"
    DATA_FRESHNESS = "data_freshness"
    COMMAND_RESPONSE = "command_response"
    GATE_COMMUNICATION = "gate_communication"
    SYSTEM_RESOURCES = "system_resources"
    DATABASE_CONNECTION = "database_connection"
    OPC_UA_SERVER = "opc_ua_server"


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    check_type: CheckType
    status: HealthStatus
    timestamp: datetime
    response_time_ms: Optional[float] = None
    details: Dict[str, any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class GateHealthStatus:
    """Health status for a specific gate"""
    gate_id: str
    last_communication: datetime
    response_time_ms: float
    command_success_rate: float
    position_accuracy: float
    consecutive_failures: int
    status: HealthStatus


@dataclass
class SCADAHealthReport:
    """Comprehensive SCADA health report"""
    timestamp: datetime
    overall_status: HealthStatus
    availability_percentage: float
    checks: List[HealthCheckResult]
    gate_statuses: Dict[str, GateHealthStatus]
    metrics: Dict[str, float]
    warnings: List[str]
    recommendations: List[str]


class SCADAHealthMonitor:
    """
    Monitors SCADA system health and availability
    """
    
    def __init__(self, scada_config: Dict, gate_registry):
        """
        Initialize SCADA health monitor
        
        Args:
            scada_config: SCADA connection configuration
            gate_registry: Gate registry for automated gates
        """
        self.config = scada_config
        self.gate_registry = gate_registry
        
        # Connection settings
        self.scada_base_url = scada_config.get("base_url", "http://scada-service:3015")
        self.opc_ua_endpoint = scada_config.get("opc_ua_endpoint", "opc.tcp://localhost:4840")
        self.health_check_interval_s = scada_config.get("health_check_interval", 30)
        
        # Thresholds
        self.thresholds = {
            "response_time_ms": {
                "healthy": 1000,
                "degraded": 3000,
                "critical": 5000
            },
            "data_staleness_s": {
                "healthy": 60,
                "degraded": 300,
                "critical": 600
            },
            "command_success_rate": {
                "healthy": 0.95,
                "degraded": 0.80,
                "critical": 0.50
            },
            "consecutive_failures": {
                "healthy": 0,
                "degraded": 3,
                "critical": 5
            },
            "availability_percentage": {
                "healthy": 99.0,
                "degraded": 95.0,
                "critical": 90.0
            }
        }
        
        # Monitoring state
        self._health_history: deque = deque(maxlen=100)
        self._gate_metrics: Dict[str, deque] = {}
        self._last_check_time: Optional[datetime] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Initialize gate metrics
        for gate_id in gate_registry.get_automated_gates_list():
            self._gate_metrics[gate_id] = deque(maxlen=50)
        
        logger.info(f"SCADA health monitor initialized for {len(self._gate_metrics)} gates")
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if self._monitoring_task:
            logger.warning("Monitoring already started")
            return
        
        self._session = aiohttp.ClientSession()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("SCADA health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        
        if self._session:
            await self._session.close()
            self._session = None
        
        logger.info("SCADA health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.health_check_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.health_check_interval_s)
    
    async def perform_health_check(self) -> SCADAHealthReport:
        """Perform comprehensive health check"""
        start_time = datetime.now()
        checks = []
        warnings = []
        recommendations = []
        
        # Perform individual checks
        checks.append(await self._check_connectivity())
        checks.append(await self._check_data_freshness())
        checks.append(await self._check_command_response())
        checks.append(await self._check_gate_communication())
        checks.append(await self._check_system_resources())
        checks.append(await self._check_opc_ua_server())
        
        # Update gate statuses
        gate_statuses = await self._update_gate_statuses()
        
        # Calculate overall status
        overall_status = self._calculate_overall_status(checks, gate_statuses)
        
        # Calculate availability
        availability = self._calculate_availability()
        
        # Generate warnings and recommendations
        warnings, recommendations = self._generate_insights(checks, gate_statuses, availability)
        
        # Create report
        report = SCADAHealthReport(
            timestamp=start_time,
            overall_status=overall_status,
            availability_percentage=availability,
            checks=checks,
            gate_statuses=gate_statuses,
            metrics=self._calculate_metrics(),
            warnings=warnings,
            recommendations=recommendations
        )
        
        # Store in history
        self._health_history.append(report)
        self._last_check_time = start_time
        
        # Log status change
        if len(self._health_history) > 1:
            prev_status = self._health_history[-2].overall_status
            if report.overall_status != prev_status:
                logger.warning(f"SCADA health status changed from {prev_status.value} "
                             f"to {report.overall_status.value}")
        
        return report
    
    async def _check_connectivity(self) -> HealthCheckResult:
        """Check basic connectivity to SCADA service"""
        start_time = datetime.now()
        
        try:
            async with self._session.get(
                f"{self.scada_base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    status = self._get_status_by_response_time(response_time)
                    return HealthCheckResult(
                        check_type=CheckType.CONNECTIVITY,
                        status=status,
                        timestamp=start_time,
                        response_time_ms=response_time,
                        details={"response": data}
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.CONNECTIVITY,
                        status=HealthStatus.FAILED,
                        timestamp=start_time,
                        response_time_ms=response_time,
                        error_message=f"HTTP {response.status}"
                    )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                check_type=CheckType.CONNECTIVITY,
                status=HealthStatus.FAILED,
                timestamp=start_time,
                error_message="Connection timeout"
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.CONNECTIVITY,
                status=HealthStatus.FAILED,
                timestamp=start_time,
                error_message=str(e)
            )
    
    async def _check_data_freshness(self) -> HealthCheckResult:
        """Check if SCADA data is fresh"""
        try:
            async with self._session.get(
                f"{self.scada_base_url}/api/v1/data/latest",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check timestamp of latest data
                    latest_timestamp = datetime.fromisoformat(data.get("timestamp", ""))
                    staleness = (datetime.now() - latest_timestamp).total_seconds()
                    
                    status = self._get_status_by_staleness(staleness)
                    
                    return HealthCheckResult(
                        check_type=CheckType.DATA_FRESHNESS,
                        status=status,
                        timestamp=datetime.now(),
                        details={
                            "latest_data_time": latest_timestamp.isoformat(),
                            "staleness_seconds": staleness
                        }
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.DATA_FRESHNESS,
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.now(),
                        error_message=f"Cannot retrieve data freshness"
                    )
        
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.DATA_FRESHNESS,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _check_command_response(self) -> HealthCheckResult:
        """Check command execution capability"""
        try:
            # Send a test command (read-only)
            test_command = {
                "command": "get_system_status",
                "parameters": {}
            }
            
            start_time = datetime.now()
            async with self._session.post(
                f"{self.scada_base_url}/api/v1/command/test",
                json=test_command,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    success = data.get("success", False)
                    
                    return HealthCheckResult(
                        check_type=CheckType.COMMAND_RESPONSE,
                        status=HealthStatus.HEALTHY if success else HealthStatus.DEGRADED,
                        timestamp=start_time,
                        response_time_ms=response_time,
                        details={"test_result": data}
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.COMMAND_RESPONSE,
                        status=HealthStatus.FAILED,
                        timestamp=start_time,
                        error_message=f"Command test failed with status {response.status}"
                    )
        
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.COMMAND_RESPONSE,
                status=HealthStatus.FAILED,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _check_gate_communication(self) -> HealthCheckResult:
        """Check communication with automated gates"""
        total_gates = len(self._gate_metrics)
        if total_gates == 0:
            return HealthCheckResult(
                check_type=CheckType.GATE_COMMUNICATION,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                details={"message": "No automated gates configured"}
            )
        
        try:
            # Get gate communication status
            async with self._session.get(
                f"{self.scada_base_url}/api/v1/gates/status",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    gates_status = data.get("gates", {})
                    
                    online_count = sum(1 for g in gates_status.values() if g.get("online", False))
                    online_percentage = (online_count / total_gates) * 100
                    
                    if online_percentage >= 95:
                        status = HealthStatus.HEALTHY
                    elif online_percentage >= 80:
                        status = HealthStatus.DEGRADED
                    elif online_percentage >= 50:
                        status = HealthStatus.CRITICAL
                    else:
                        status = HealthStatus.FAILED
                    
                    return HealthCheckResult(
                        check_type=CheckType.GATE_COMMUNICATION,
                        status=status,
                        timestamp=datetime.now(),
                        details={
                            "total_gates": total_gates,
                            "online_gates": online_count,
                            "online_percentage": online_percentage
                        }
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.GATE_COMMUNICATION,
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.now(),
                        error_message="Cannot retrieve gate status"
                    )
        
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.GATE_COMMUNICATION,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _check_system_resources(self) -> HealthCheckResult:
        """Check SCADA system resource usage"""
        try:
            async with self._session.get(
                f"{self.scada_base_url}/api/v1/system/resources",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    cpu_usage = data.get("cpu_usage_percent", 0)
                    memory_usage = data.get("memory_usage_percent", 0)
                    disk_usage = data.get("disk_usage_percent", 0)
                    
                    # Determine status based on resource usage
                    if cpu_usage > 90 or memory_usage > 90 or disk_usage > 95:
                        status = HealthStatus.CRITICAL
                    elif cpu_usage > 70 or memory_usage > 70 or disk_usage > 85:
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.HEALTHY
                    
                    return HealthCheckResult(
                        check_type=CheckType.SYSTEM_RESOURCES,
                        status=status,
                        timestamp=datetime.now(),
                        details={
                            "cpu_usage_percent": cpu_usage,
                            "memory_usage_percent": memory_usage,
                            "disk_usage_percent": disk_usage
                        }
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.SYSTEM_RESOURCES,
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.now(),
                        error_message="Cannot retrieve resource usage"
                    )
        
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.SYSTEM_RESOURCES,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _check_opc_ua_server(self) -> HealthCheckResult:
        """Check OPC UA server connection"""
        try:
            async with self._session.get(
                f"{self.scada_base_url}/api/v1/opcua/status",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    connected = data.get("connected", False)
                    
                    if connected:
                        server_state = data.get("server_state", "Unknown")
                        if server_state == "Running":
                            status = HealthStatus.HEALTHY
                        else:
                            status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.FAILED
                    
                    return HealthCheckResult(
                        check_type=CheckType.OPC_UA_SERVER,
                        status=status,
                        timestamp=datetime.now(),
                        details=data
                    )
                else:
                    return HealthCheckResult(
                        check_type=CheckType.OPC_UA_SERVER,
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.now(),
                        error_message="Cannot retrieve OPC UA status"
                    )
        
        except Exception as e:
            return HealthCheckResult(
                check_type=CheckType.OPC_UA_SERVER,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def _update_gate_statuses(self) -> Dict[str, GateHealthStatus]:
        """Update health status for each gate"""
        gate_statuses = {}
        
        try:
            # Get gate-specific metrics
            async with self._session.get(
                f"{self.scada_base_url}/api/v1/gates/metrics",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for gate_id in self._gate_metrics:
                        gate_data = data.get(gate_id, {})
                        
                        # Create health status
                        last_comm = gate_data.get("last_communication")
                        if last_comm:
                            last_comm = datetime.fromisoformat(last_comm)
                        else:
                            last_comm = datetime.now() - timedelta(hours=1)
                        
                        response_time = gate_data.get("avg_response_time_ms", 0)
                        success_rate = gate_data.get("command_success_rate", 0)
                        position_accuracy = gate_data.get("position_accuracy", 0)
                        failures = gate_data.get("consecutive_failures", 0)
                        
                        # Determine gate status
                        if failures >= self.thresholds["consecutive_failures"]["critical"]:
                            status = HealthStatus.FAILED
                        elif failures >= self.thresholds["consecutive_failures"]["degraded"]:
                            status = HealthStatus.CRITICAL
                        elif success_rate < self.thresholds["command_success_rate"]["critical"]:
                            status = HealthStatus.CRITICAL
                        elif success_rate < self.thresholds["command_success_rate"]["degraded"]:
                            status = HealthStatus.DEGRADED
                        else:
                            status = HealthStatus.HEALTHY
                        
                        gate_statuses[gate_id] = GateHealthStatus(
                            gate_id=gate_id,
                            last_communication=last_comm,
                            response_time_ms=response_time,
                            command_success_rate=success_rate,
                            position_accuracy=position_accuracy,
                            consecutive_failures=failures,
                            status=status
                        )
                        
                        # Store in metrics history
                        self._gate_metrics[gate_id].append({
                            "timestamp": datetime.now(),
                            "status": status,
                            "response_time": response_time,
                            "success_rate": success_rate
                        })
        
        except Exception as e:
            logger.error(f"Failed to update gate statuses: {e}")
        
        return gate_statuses
    
    def _calculate_overall_status(self, checks: List[HealthCheckResult], 
                                gate_statuses: Dict[str, GateHealthStatus]) -> HealthStatus:
        """Calculate overall SCADA health status"""
        # Count check statuses
        check_counts = {status: 0 for status in HealthStatus}
        for check in checks:
            check_counts[check.status] += 1
        
        # Count gate statuses
        gate_counts = {status: 0 for status in HealthStatus}
        for gate_status in gate_statuses.values():
            gate_counts[gate_status.status] += 1
        
        # Determine overall status (worst case)
        if check_counts[HealthStatus.FAILED] > 0 or gate_counts[HealthStatus.FAILED] > len(gate_statuses) * 0.2:
            return HealthStatus.FAILED
        elif check_counts[HealthStatus.CRITICAL] > 0 or gate_counts[HealthStatus.CRITICAL] > len(gate_statuses) * 0.1:
            return HealthStatus.CRITICAL
        elif check_counts[HealthStatus.DEGRADED] > 1 or gate_counts[HealthStatus.DEGRADED] > len(gate_statuses) * 0.2:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _calculate_availability(self) -> float:
        """Calculate system availability percentage"""
        if not self._health_history:
            return 100.0
        
        # Calculate based on recent history
        total_checks = len(self._health_history)
        healthy_checks = sum(1 for report in self._health_history 
                           if report.overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED])
        
        return (healthy_checks / total_checks) * 100 if total_checks > 0 else 0.0
    
    def _calculate_metrics(self) -> Dict[str, float]:
        """Calculate aggregate metrics"""
        metrics = {}
        
        if self._health_history:
            # Average response times
            response_times = []
            for report in self._health_history:
                for check in report.checks:
                    if check.response_time_ms:
                        response_times.append(check.response_time_ms)
            
            if response_times:
                metrics["avg_response_time_ms"] = statistics.mean(response_times)
                metrics["p95_response_time_ms"] = statistics.quantiles(response_times, n=20)[18]
            
            # Gate metrics
            online_gates = []
            for report in self._health_history:
                online_count = sum(1 for gs in report.gate_statuses.values() 
                                 if gs.status != HealthStatus.FAILED)
                online_gates.append(online_count)
            
            if online_gates:
                metrics["avg_online_gates"] = statistics.mean(online_gates)
                metrics["min_online_gates"] = min(online_gates)
        
        return metrics
    
    def _generate_insights(self, checks: List[HealthCheckResult], 
                         gate_statuses: Dict[str, GateHealthStatus],
                         availability: float) -> Tuple[List[str], List[str]]:
        """Generate warnings and recommendations"""
        warnings = []
        recommendations = []
        
        # Check-based warnings
        for check in checks:
            if check.status == HealthStatus.FAILED:
                warnings.append(f"{check.check_type.value} check failed: {check.error_message}")
            elif check.status == HealthStatus.CRITICAL:
                warnings.append(f"{check.check_type.value} check is critical")
        
        # Gate-based warnings
        failed_gates = [gs.gate_id for gs in gate_statuses.values() if gs.status == HealthStatus.FAILED]
        if failed_gates:
            warnings.append(f"{len(failed_gates)} gates have failed: {', '.join(failed_gates[:5])}")
        
        # Availability warning
        if availability < self.thresholds["availability_percentage"]["critical"]:
            warnings.append(f"System availability critically low: {availability:.1f}%")
        
        # Generate recommendations
        if any(check.check_type == CheckType.CONNECTIVITY and 
              check.status != HealthStatus.HEALTHY for check in checks):
            recommendations.append("Check network connectivity to SCADA service")
        
        if any(check.check_type == CheckType.OPC_UA_SERVER and 
              check.status == HealthStatus.FAILED for check in checks):
            recommendations.append("Restart OPC UA server or check iFix connection")
        
        if len(failed_gates) > 0:
            recommendations.append(f"Investigate failed gates and dispatch field teams if needed")
        
        if availability < 95:
            recommendations.append("Review system logs for root cause of availability issues")
        
        return warnings, recommendations
    
    def _get_status_by_response_time(self, response_time_ms: float) -> HealthStatus:
        """Get health status based on response time"""
        thresholds = self.thresholds["response_time_ms"]
        
        if response_time_ms <= thresholds["healthy"]:
            return HealthStatus.HEALTHY
        elif response_time_ms <= thresholds["degraded"]:
            return HealthStatus.DEGRADED
        elif response_time_ms <= thresholds["critical"]:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.FAILED
    
    def _get_status_by_staleness(self, staleness_s: float) -> HealthStatus:
        """Get health status based on data staleness"""
        thresholds = self.thresholds["data_staleness_s"]
        
        if staleness_s <= thresholds["healthy"]:
            return HealthStatus.HEALTHY
        elif staleness_s <= thresholds["degraded"]:
            return HealthStatus.DEGRADED
        elif staleness_s <= thresholds["critical"]:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.FAILED
    
    async def get_current_status(self) -> Optional[SCADAHealthReport]:
        """Get the most recent health report"""
        if self._health_history:
            return self._health_history[-1]
        return None
    
    async def get_gate_availability(self, gate_id: str, 
                                  time_window: timedelta = timedelta(hours=1)) -> float:
        """Get availability percentage for a specific gate"""
        if gate_id not in self._gate_metrics:
            return 0.0
        
        cutoff_time = datetime.now() - time_window
        metrics = self._gate_metrics[gate_id]
        
        relevant_metrics = [m for m in metrics if m["timestamp"] > cutoff_time]
        if not relevant_metrics:
            return 0.0
        
        available_count = sum(1 for m in relevant_metrics 
                            if m["status"] != HealthStatus.FAILED)
        
        return (available_count / len(relevant_metrics)) * 100
    
    def is_scada_available(self) -> bool:
        """Quick check if SCADA is available for operations"""
        if not self._health_history:
            return False
        
        latest = self._health_history[-1]
        return latest.overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
    
    def get_failed_gates(self) -> List[str]:
        """Get list of currently failed gates"""
        if not self._health_history:
            return []
        
        latest = self._health_history[-1]
        return [gate_id for gate_id, status in latest.gate_statuses.items() 
                if status.status == HealthStatus.FAILED]