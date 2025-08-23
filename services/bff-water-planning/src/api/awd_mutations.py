import strawberry
from typing import Optional, List
from datetime import datetime

from ..context import GraphQLContext
from services.awd_integration import AWDIntegrationService
from core import get_logger

logger = get_logger(__name__)


@strawberry.input
class AWDMonitoringInput:
    """Input for AWD monitoring data update"""
    plot_id: str
    moisture_level: float
    timestamp: Optional[datetime] = None


@strawberry.input
class AWDActivationInput:
    """Input for AWD activation"""
    plot_id: str
    dry_threshold: float = 15.0  # cm below surface
    wet_threshold: float = 5.0   # cm below surface
    monitoring_interval_hours: int = 24


@strawberry.type
class AWDStatus:
    """AWD status response"""
    plot_id: str
    is_active: bool
    current_phase: str
    moisture_level: Optional[float]
    last_irrigation: Optional[datetime]
    next_check: Optional[datetime]
    recommendation: str
    expected_savings_m3: float


@strawberry.type
class AWDActivationResult:
    """Result of AWD activation"""
    success: bool
    plot_id: str
    message: str
    awd_parameters: Optional[dict] = None
    estimated_annual_savings_m3: Optional[float] = None


@strawberry.type
class AWDMutations:
    """AWD-related mutations"""
    
    @strawberry.mutation
    async def update_awd_monitoring(
        self,
        info: strawberry.Info[GraphQLContext],
        input: AWDMonitoringInput
    ) -> AWDStatus:
        """Update AWD monitoring data from field sensors"""
        awd_service = AWDIntegrationService()
        
        try:
            # Update moisture reading
            success = await awd_service.update_awd_monitoring_data(
                plot_id=input.plot_id,
                moisture_level=input.moisture_level
            )
            
            if not success:
                logger.error(
                    "Failed to update AWD monitoring",
                    plot_id=input.plot_id,
                    moisture=input.moisture_level
                )
            
            # Get updated status
            client = awd_service.client
            status = await client.get_plot_status(input.plot_id)
            
            if status:
                return AWDStatus(
                    plot_id=input.plot_id,
                    is_active=status.get("is_active", False),
                    current_phase=status.get("current_phase", "unknown"),
                    moisture_level=input.moisture_level,
                    last_irrigation=status.get("last_irrigation"),
                    next_check=status.get("next_check"),
                    recommendation=status.get("recommendation", ""),
                    expected_savings_m3=status.get("expected_savings", 0)
                )
            else:
                # Return default if status not found
                return AWDStatus(
                    plot_id=input.plot_id,
                    is_active=False,
                    current_phase="inactive",
                    moisture_level=input.moisture_level,
                    last_irrigation=None,
                    next_check=None,
                    recommendation="AWD not configured for this plot",
                    expected_savings_m3=0
                )
                
        finally:
            await awd_service.close()
    
    @strawberry.mutation
    async def activate_awd_mode(
        self,
        info: strawberry.Info[GraphQLContext],
        input: AWDActivationInput
    ) -> AWDActivationResult:
        """Activate AWD mode for a specific plot"""
        awd_service = AWDIntegrationService()
        
        try:
            # Prepare AWD parameters
            parameters = {
                "dry_threshold": input.dry_threshold,
                "wet_threshold": input.wet_threshold,
                "monitoring_interval_hours": input.monitoring_interval_hours
            }
            
            # Activate AWD
            result = await awd_service.client.activate_awd(
                plot_id=input.plot_id,
                parameters=parameters
            )
            
            if result:
                logger.info(
                    "AWD activated",
                    plot_id=input.plot_id,
                    parameters=parameters,
                    client_type=info.context.client_type
                )
                
                return AWDActivationResult(
                    success=True,
                    plot_id=input.plot_id,
                    message="AWD mode activated successfully",
                    awd_parameters=parameters,
                    estimated_annual_savings_m3=result.get("estimated_annual_savings", 0)
                )
            else:
                return AWDActivationResult(
                    success=False,
                    plot_id=input.plot_id,
                    message="Failed to activate AWD mode",
                    awd_parameters=None,
                    estimated_annual_savings_m3=None
                )
                
        except Exception as e:
            logger.error(
                "Error activating AWD",
                plot_id=input.plot_id,
                error=str(e)
            )
            return AWDActivationResult(
                success=False,
                plot_id=input.plot_id,
                message=f"Error: {str(e)}",
                awd_parameters=None,
                estimated_annual_savings_m3=None
            )
        finally:
            await awd_service.close()
    
    @strawberry.mutation
    async def deactivate_awd_mode(
        self,
        info: strawberry.Info[GraphQLContext],
        plot_id: str,
        reason: str = ""
    ) -> bool:
        """Deactivate AWD mode for a plot"""
        awd_service = AWDIntegrationService()
        
        try:
            success = await awd_service.client.deactivate_awd(plot_id, reason)
            
            if success:
                logger.info(
                    "AWD deactivated",
                    plot_id=plot_id,
                    reason=reason,
                    client_type=info.context.client_type
                )
            
            return success
            
        finally:
            await awd_service.close()
    
    @strawberry.mutation
    async def batch_update_awd_monitoring(
        self,
        info: strawberry.Info[GraphQLContext],
        updates: List[AWDMonitoringInput]
    ) -> List[AWDStatus]:
        """Batch update AWD monitoring data"""
        awd_service = AWDIntegrationService()
        results = []
        
        try:
            for update in updates:
                # Update each plot
                await awd_service.update_awd_monitoring_data(
                    plot_id=update.plot_id,
                    moisture_level=update.moisture_level
                )
            
            # Get all statuses
            plot_ids = [u.plot_id for u in updates]
            statuses = await awd_service.client.get_batch_status(plot_ids)
            
            for update in updates:
                status = statuses.get(update.plot_id, {})
                results.append(AWDStatus(
                    plot_id=update.plot_id,
                    is_active=status.get("is_active", False),
                    current_phase=status.get("current_phase", "unknown"),
                    moisture_level=update.moisture_level,
                    last_irrigation=status.get("last_irrigation"),
                    next_check=status.get("next_check"),
                    recommendation=status.get("recommendation", ""),
                    expected_savings_m3=status.get("expected_savings", 0)
                ))
            
            logger.info(
                "Batch AWD update completed",
                count=len(updates),
                client_type=info.context.client_type
            )
            
            return results
            
        finally:
            await awd_service.close()