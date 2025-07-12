from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import structlog

from db import DatabaseManager
from schemas import VolumeData, WaterBalance
from core.metrics import total_volume as total_volume_metric

logger = structlog.get_logger()


class VolumeService:
    """Service for volume calculations and water balance"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def calculate_cumulative_volume(
        self,
        location_id: UUID,
        start_time: datetime,
        end_time: datetime,
        channel_id: str = "main"
    ) -> VolumeData:
        """Calculate cumulative volume over a time period"""
        try:
            # Get flow data from InfluxDB
            data = await self.db.influxdb.query_flow_data(
                location_id=str(location_id),
                start_time=start_time,
                end_time=end_time,
                aggregation="mean",
                interval="5m"  # 5-minute intervals for accuracy
            )
            
            # Extract flow rates
            flow_rates = []
            timestamps = []
            for record in data:
                if record["field"] == "flow_rate":
                    flow_rates.append(record["value"])
                    timestamps.append(record["time"])
            
            if not flow_rates:
                return VolumeData(
                    location_id=location_id,
                    channel_id=channel_id,
                    start_time=start_time,
                    end_time=end_time,
                    total_volume=0.0,
                    average_flow_rate=0.0,
                    peak_flow_rate=0.0,
                    min_flow_rate=0.0
                )
            
            # Calculate volume using trapezoidal integration
            total_volume = 0.0
            for i in range(1, len(flow_rates)):
                # Time difference in seconds
                dt = (timestamps[i] - timestamps[i-1]).total_seconds()
                # Average flow rate for interval
                avg_flow = (flow_rates[i] + flow_rates[i-1]) / 2
                # Volume = flow rate * time
                total_volume += avg_flow * dt
            
            # Calculate statistics
            average_flow = sum(flow_rates) / len(flow_rates)
            peak_flow = max(flow_rates)
            min_flow = min(flow_rates)
            
            # Update metrics
            total_volume_metric.labels(
                location_id=str(location_id),
                period="custom"
            ).set(total_volume)
            
            return VolumeData(
                location_id=location_id,
                channel_id=channel_id,
                start_time=start_time,
                end_time=end_time,
                total_volume=total_volume,
                average_flow_rate=average_flow,
                peak_flow_rate=peak_flow,
                min_flow_rate=min_flow
            )
            
        except Exception as e:
            logger.error("Failed to calculate cumulative volume", error=str(e))
            raise
    
    async def calculate_water_balance(
        self,
        segment_id: UUID,
        start_time: datetime,
        end_time: datetime
    ) -> WaterBalance:
        """Calculate water balance for a network segment"""
        try:
            # Get segment configuration (simplified for now)
            # In production, this would come from a segments table
            segment_name = f"Segment {segment_id}"
            
            # Get all inflow and outflow locations for the segment
            # Simplified: assuming we have this mapping
            inflow_locations = []  # Would be fetched from DB
            outflow_locations = []  # Would be fetched from DB
            
            # Calculate inflow volume
            inflow_volume = 0.0
            inflow_details = []
            
            for location in inflow_locations:
                volume_data = await self.calculate_cumulative_volume(
                    location_id=location["id"],
                    start_time=start_time,
                    end_time=end_time
                )
                inflow_volume += volume_data.total_volume
                inflow_details.append({
                    "location_id": str(location["id"]),
                    "location_name": location["name"],
                    "volume": volume_data.total_volume
                })
            
            # Calculate outflow volume
            outflow_volume = 0.0
            outflow_details = []
            
            for location in outflow_locations:
                volume_data = await self.calculate_cumulative_volume(
                    location_id=location["id"],
                    start_time=start_time,
                    end_time=end_time
                )
                outflow_volume += volume_data.total_volume
                outflow_details.append({
                    "location_id": str(location["id"]),
                    "location_name": location["name"],
                    "volume": volume_data.total_volume
                })
            
            # Calculate balance and losses
            balance_volume = inflow_volume - outflow_volume
            
            # Estimate losses (simplified model)
            # In production, these would use more sophisticated models
            time_hours = (end_time - start_time).total_seconds() / 3600
            
            # Seepage: assume 2% per day
            seepage_rate = 0.02 / 24  # per hour
            estimated_seepage = inflow_volume * seepage_rate * time_hours
            
            # Evaporation: assume 0.5% per day (varies by season)
            evaporation_rate = 0.005 / 24  # per hour
            estimated_evaporation = inflow_volume * evaporation_rate * time_hours
            
            # Unaccounted loss
            total_estimated_loss = estimated_seepage + estimated_evaporation
            unaccounted_loss = max(0, balance_volume - total_estimated_loss)
            total_loss = balance_volume
            
            # Calculate efficiency
            if inflow_volume > 0:
                efficiency_percent = (outflow_volume / inflow_volume) * 100
                loss_percent = (total_loss / inflow_volume) * 100
            else:
                efficiency_percent = 0
                loss_percent = 0
            
            # Create water balance record
            water_balance = WaterBalance(
                segment_id=segment_id,
                segment_name=segment_name,
                time=end_time,
                time_period=f"{time_hours:.1f} hours",
                inflow_volume=inflow_volume,
                outflow_volume=outflow_volume,
                balance_volume=balance_volume,
                estimated_seepage=estimated_seepage,
                estimated_evaporation=estimated_evaporation,
                unaccounted_loss=unaccounted_loss,
                total_loss=total_loss,
                efficiency_percent=efficiency_percent,
                loss_percent=loss_percent,
                inflow_locations=inflow_details,
                outflow_locations=outflow_details
            )
            
            # Store in database
            await self.db.timescale.insert_water_balance(water_balance.dict())
            
            return water_balance
            
        except Exception as e:
            logger.error("Failed to calculate water balance", error=str(e))
            raise
    
    async def get_daily_volumes(
        self,
        location_ids: List[UUID],
        start_time: datetime,
        end_time: datetime
    ) -> List[VolumeData]:
        """Get daily volume totals for multiple locations"""
        try:
            results = []
            
            # Calculate for each location
            for location_id in location_ids:
                # Get daily aggregates
                current_day = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                
                while current_day < end_time:
                    next_day = current_day + timedelta(days=1)
                    
                    volume_data = await self.calculate_cumulative_volume(
                        location_id=location_id,
                        start_time=current_day,
                        end_time=next_day
                    )
                    
                    results.append(volume_data)
                    current_day = next_day
            
            return results
            
        except Exception as e:
            logger.error("Failed to get daily volumes", error=str(e))
            raise
    
    async def get_balance_history(
        self,
        segment_id: UUID,
        start_time: datetime,
        end_time: datetime,
        offset: int = 0,
        limit: int = 50
    ) -> Tuple[List[WaterBalance], int]:
        """Get historical water balance records"""
        try:
            # Query from TimescaleDB
            async with self.db.timescale.pool.acquire() as conn:
                # Get total count
                count_row = await conn.fetchrow('''
                    SELECT COUNT(*) as total
                    FROM water_balance
                    WHERE segment_id = $1
                        AND time >= $2
                        AND time <= $3
                ''', segment_id, start_time, end_time)
                
                total = count_row["total"]
                
                # Get paginated results
                rows = await conn.fetch('''
                    SELECT *
                    FROM water_balance
                    WHERE segment_id = $1
                        AND time >= $2
                        AND time <= $3
                    ORDER BY time DESC
                    OFFSET $4
                    LIMIT $5
                ''', segment_id, start_time, end_time, offset, limit)
                
                # Convert to WaterBalance objects
                balances = []
                for row in rows:
                    balance = WaterBalance(
                        segment_id=row["segment_id"],
                        segment_name=f"Segment {row['segment_id']}",
                        time=row["time"],
                        time_period="1 day",  # Simplified
                        inflow_volume=float(row["inflow_volume"]),
                        outflow_volume=float(row["outflow_volume"]),
                        balance_volume=float(row["balance_volume"]),
                        estimated_seepage=float(row.get("estimated_seepage", 0)),
                        estimated_evaporation=float(row.get("estimated_evaporation", 0)),
                        unaccounted_loss=float(row.get("unaccounted_loss", 0)),
                        total_loss=float(row["loss_volume"]),
                        efficiency_percent=float(row["efficiency_percent"]),
                        loss_percent=100 - float(row["efficiency_percent"]),
                        inflow_locations=[],  # Would be stored as JSONB
                        outflow_locations=[]  # Would be stored as JSONB
                    )
                    balances.append(balance)
                
                return balances, total
                
        except Exception as e:
            logger.error("Failed to get balance history", error=str(e))
            raise
    
    async def trigger_balance_calculations(
        self,
        segment_ids: List[UUID]
    ) -> Dict[str, Any]:
        """Trigger water balance calculations for multiple segments"""
        try:
            results = {
                "triggered": [],
                "failed": []
            }
            
            # Calculate balance for last 24 hours
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            for segment_id in segment_ids:
                try:
                    await self.calculate_water_balance(
                        segment_id=segment_id,
                        start_time=start_time,
                        end_time=end_time
                    )
                    results["triggered"].append(str(segment_id))
                except Exception as e:
                    logger.error(f"Failed to calculate balance for segment {segment_id}", error=str(e))
                    results["failed"].append({
                        "segment_id": str(segment_id),
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error("Failed to trigger balance calculations", error=str(e))
            raise