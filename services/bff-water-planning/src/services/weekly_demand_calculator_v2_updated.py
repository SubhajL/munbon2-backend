"""
Updated methods for weekly_demand_calculator_v2.py to integrate water level data
This file contains the updated methods that should replace the existing ones
"""

async def _get_last_week_sensor_adjustments(self) -> Dict[str, float]:
    """Get sensor-based adjustment factors from water level data"""
    try:
        # Get last week's Monday
        today = date.today()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        
        logger.info(f"Fetching water level adjustments for week {last_monday} to {last_sunday}")
        
        # Query to get average water levels and calculate adjustments
        query = """
            SELECT 
                wla.section_id,
                AVG(wla.avg_water_level_m) as avg_water_level,
                -- Get thresholds
                MAX(CASE WHEN wlt.threshold_type = 'critical_low' THEN wlt.water_level_m END) as critical_low,
                MAX(CASE WHEN wlt.threshold_type = 'warning_low' THEN wlt.water_level_m END) as warning_low,
                MAX(CASE WHEN wlt.threshold_type = 'optimal' THEN wlt.water_level_m END) as optimal,
                MAX(CASE WHEN wlt.threshold_type = 'warning_high' THEN wlt.water_level_m END) as warning_high,
                MAX(CASE WHEN wlt.threshold_type = 'critical_high' THEN wlt.water_level_m END) as critical_high
            FROM ros_gis.water_level_aggregations wla
            LEFT JOIN ros_gis.water_level_thresholds wlt ON wla.section_id = wlt.section_id
                AND wlt.effective_date <= $2
                AND (wlt.expires_date IS NULL OR wlt.expires_date >= $2)
            WHERE wla.date BETWEEN $1 AND $2
            GROUP BY wla.section_id
        """
        
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(query, last_monday, last_sunday)
            
            adjustments = {}
            
            for row in rows:
                section_id = row['section_id']
                avg_level = float(row['avg_water_level']) if row['avg_water_level'] else None
                
                if avg_level is None:
                    continue
                
                # Calculate adjustment factor using the database function
                adjustment_query = """
                    SELECT ros_gis.calculate_water_adjustment_factor(
                        $1::DECIMAL, $2::DECIMAL, $3::DECIMAL, 
                        $4::DECIMAL, $5::DECIMAL, $6::DECIMAL
                    ) as adjustment_factor
                """
                
                result = await conn.fetchrow(
                    adjustment_query,
                    avg_level,
                    row['critical_low'] or 0.02,
                    row['warning_low'] or 0.05,
                    row['optimal'] or 0.10,
                    row['warning_high'] or 0.15,
                    row['critical_high'] or 0.20
                )
                
                adjustment_factor = float(result['adjustment_factor'])
                adjustments[section_id] = adjustment_factor
                
                # Log significant adjustments
                if adjustment_factor < 0.8 or adjustment_factor > 1.1:
                    logger.info(
                        f"Section {section_id}: Water level {avg_level:.3f}m, "
                        f"Adjustment factor: {adjustment_factor:.2f}"
                    )
            
            logger.info(f"Retrieved water level adjustments for {len(adjustments)} sections")
            
            # Get current week's water levels for storage
            current_monday = today - timedelta(days=today.weekday())
            current_levels_query = """
                SELECT section_id, AVG(avg_water_level_m) as avg_level
                FROM ros_gis.water_level_aggregations
                WHERE date >= $1
                GROUP BY section_id
            """
            
            current_levels = await conn.fetch(current_levels_query, current_monday)
            self._current_water_levels = {
                row['section_id']: float(row['avg_level']) 
                for row in current_levels if row['avg_level']
            }
            
            return adjustments
            
    except Exception as e:
        logger.error(f"Failed to get water level adjustments: {str(e)}")
        # Return empty dict on error to continue with no adjustment
        return {}


async def _store_weekly_demand(
    self,
    demand: Dict,
    sensor_adjustment: float,
    area_type: str
):
    """Store calculated demand in database with water level info"""
    demand['sensor_adjustment_factor'] = sensor_adjustment
    demand['adjusted_demand_m3'] = demand['gross_demand_m3'] * sensor_adjustment
    
    # Add water level information if available
    section_id = demand.get('area_id')
    if hasattr(self, '_current_water_levels') and section_id in self._current_water_levels:
        demand['water_level_m'] = self._current_water_levels[section_id]
        
        # Determine water level status
        if demand['water_level_m'] < 0.02:
            demand['water_level_status'] = 'CRITICAL_LOW'
        elif demand['water_level_m'] < 0.05:
            demand['water_level_status'] = 'WARNING_LOW'
        elif demand['water_level_m'] < 0.10:
            demand['water_level_status'] = 'OPTIMAL'
        elif demand['water_level_m'] < 0.15:
            demand['water_level_status'] = 'WARNING_HIGH'
        elif demand['water_level_m'] < 0.20:
            demand['water_level_status'] = 'CRITICAL_HIGH'
        else:
            demand['water_level_status'] = 'ABOVE_CRITICAL'
        
        demand['water_level_adjustment_applied'] = sensor_adjustment != 1.0
    
    await self.repository.store_weekly_demand(demand)


async def _update_season_progress(self, week_start: date):
    """Update crop season progress tracking with water level info"""
    try:
        logger.info("Updating crop season progress with water level data")
        
        async with self.db.get_connection() as conn:
            # Update crop progress with water level status
            update_query = """
                UPDATE ros_gis.crop_season_weekly_progress csp
                SET 
                    avg_water_level_m = wla.avg_level,
                    water_level_status = CASE
                        WHEN wla.avg_level < 0.02 THEN 'CRITICAL_LOW'
                        WHEN wla.avg_level < 0.05 THEN 'WARNING_LOW'
                        WHEN wla.avg_level < 0.10 THEN 'OPTIMAL'
                        WHEN wla.avg_level < 0.15 THEN 'WARNING_HIGH'
                        WHEN wla.avg_level < 0.20 THEN 'CRITICAL_HIGH'
                        ELSE 'ABOVE_CRITICAL'
                    END,
                    water_stress_days = CASE
                        WHEN wla.avg_level < 0.05 THEN 
                            COALESCE(csp.water_stress_days, 0) + 7
                        ELSE 
                            COALESCE(csp.water_stress_days, 0)
                    END,
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT section_id, AVG(avg_water_level_m) as avg_level
                    FROM ros_gis.water_level_aggregations
                    WHERE date >= $1 AND date < $1 + INTERVAL '7 days'
                    GROUP BY section_id
                ) wla
                WHERE csp.area_id = wla.section_id
                AND csp.week_start_date = $1
                AND csp.area_type = 'section'
            """
            
            result = await conn.execute(update_query, week_start)
            
            # Also update zone and munbon totals
            zone_update_query = """
                UPDATE ros_gis.crop_season_weekly_progress csp
                SET 
                    avg_water_level_m = zone_wl.avg_level,
                    water_level_status = zone_wl.status,
                    water_stress_days = zone_wl.stress_days,
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT 
                        SUBSTRING(area_id FROM 1 FOR 5) as zone_id,
                        AVG(avg_water_level_m) as avg_level,
                        MODE() WITHIN GROUP (ORDER BY water_level_status) as status,
                        MAX(water_stress_days) as stress_days
                    FROM ros_gis.crop_season_weekly_progress
                    WHERE week_start_date = $1
                    AND area_type = 'section'
                    GROUP BY SUBSTRING(area_id FROM 1 FOR 5)
                ) zone_wl
                WHERE csp.area_id = zone_wl.zone_id
                AND csp.week_start_date = $1
                AND csp.area_type = 'zone'
            """
            
            await conn.execute(zone_update_query, week_start)
            
            logger.info("Crop season progress updated with water level data")
            
    except Exception as e:
        logger.error(f"Failed to update season progress: {str(e)}")
        # Continue even if update fails