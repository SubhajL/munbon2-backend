from typing import List, Optional, Dict
from collections import defaultdict
from .base_loader import BaseDataLoader


class PlotLoader(BaseDataLoader):
    """DataLoader for batch loading plots by section ID"""
    
    async def batch_load_fn(self, section_ids: List[str]) -> List[List[Dict]]:
        """
        Batch load plots for multiple sections
        
        Args:
            section_ids: List of section IDs to load plots for
            
        Returns:
            List of plot lists in same order as requested section IDs
        """
        if not section_ids:
            return []
        
        self.logger.info(f"Batch loading plots for {len(section_ids)} sections")
        
        # Single query to get all plots for all sections
        query = """
            SELECT 
                p.plot_code,
                p.section_code,
                p.area_rai,
                p.crop_type,
                p.planting_date,
                p.status,
                ST_AsGeoJSON(ST_Centroid(p.geometry)) as centroid,
                p.properties
            FROM gis.agricultural_plots p
            WHERE p.section_code = ANY($1::text[])
            ORDER BY p.section_code, p.plot_code
        """
        
        results = await self.db.fetch_all(query, section_ids)
        
        # Group plots by section
        plots_by_section = defaultdict(list)
        for row in results:
            plot = {
                "plot_code": row["plot_code"],
                "area_rai": float(row["area_rai"]) if row["area_rai"] else 0,
                "crop_type": row["crop_type"],
                "planting_date": row["planting_date"],
                "status": row["status"],
                "centroid": row["centroid"],
                "properties": row["properties"] or {}
            }
            plots_by_section[row["section_code"]].append(plot)
        
        # Return plots in same order as requested sections
        return [plots_by_section.get(section_id, []) for section_id in section_ids]