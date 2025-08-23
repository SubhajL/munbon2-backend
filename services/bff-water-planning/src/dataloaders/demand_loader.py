from typing import List, Optional, Dict, Tuple
from datetime import datetime
from .base_loader import BaseDataLoader


class DemandLoader(BaseDataLoader):
    """DataLoader for batch loading water demands"""
    
    async def batch_load_fn(
        self, 
        keys: List[Tuple[str, datetime, str]]
    ) -> List[Optional[Dict]]:
        """
        Batch load demands by (level_id, date, method) tuples
        
        Args:
            keys: List of (level_id, date, method) tuples
            
        Returns:
            List of demand data in same order as requested keys
        """
        if not keys:
            return []
        
        self.logger.info(f"Batch loading {len(keys)} demands")
        
        # Extract unique components
        level_ids = list(set(k[0] for k in keys))
        dates = list(set(k[1] for k in keys))
        methods = list(set(k[2] for k in keys))
        
        # Single query to get all demands
        query = """
            SELECT 
                level_id,
                demand_date,
                method,
                level_type,
                gross_demand_m3,
                effective_rainfall_m3,
                net_demand_m3,
                area_rai,
                metadata
            FROM gis.water_demand_daily
            WHERE level_id = ANY($1::text[])
                AND demand_date = ANY($2::date[])
                AND method = ANY($3::text[])
        """
        
        results = await self.db.fetch_all(query, level_ids, dates, methods)
        
        # Create lookup map
        demand_map = {}
        for row in results:
            key = (
                row["level_id"], 
                row["demand_date"].isoformat(), 
                row["method"]
            )
            demand_map[key] = {
                "level_id": row["level_id"],
                "demand_date": row["demand_date"],
                "method": row["method"],
                "level_type": row["level_type"],
                "gross_demand_m3": float(row["gross_demand_m3"] or 0),
                "effective_rainfall_m3": float(row["effective_rainfall_m3"] or 0),
                "net_demand_m3": float(row["net_demand_m3"] or 0),
                "area_rai": float(row["area_rai"] or 0),
                "metadata": row["metadata"] or {}
            }
        
        # Return in requested order
        return [
            demand_map.get((k[0], k[1].isoformat(), k[2])) 
            for k in keys
        ]