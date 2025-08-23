from typing import List, Optional, Dict
from .base_loader import BaseDataLoader


class SectionLoader(BaseDataLoader):
    """DataLoader for batch loading sections by ID"""
    
    async def batch_load_fn(self, section_ids: List[str]) -> List[Optional[Dict]]:
        """
        Batch load sections by IDs
        
        Args:
            section_ids: List of section IDs to load
            
        Returns:
            List of section data in same order as requested IDs
        """
        if not section_ids:
            return []
        
        self.logger.info(f"Batch loading {len(section_ids)} sections")
        
        # Single query to get all sections
        query = """
            SELECT 
                s.section_code,
                s.section_name,
                s.zone_code,
                s.area_rai,
                s.plot_count,
                ST_AsGeoJSON(s.geometry) as geometry,
                s.created_at,
                s.updated_at
            FROM gis.sections s
            WHERE s.section_code = ANY($1::text[])
        """
        
        results = await self.db.fetch_all(query, section_ids)
        
        # Convert to dict format
        sections = []
        for row in results:
            sections.append({
                "id": row["section_code"],
                "name": row["section_name"],
                "zone_code": row["zone_code"],
                "area_rai": float(row["area_rai"]) if row["area_rai"] else 0,
                "plot_count": row["plot_count"] or 0,
                "geometry": row["geometry"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        
        # Map results back to requested order
        return self._map_results_to_keys(section_ids, sections, "id")