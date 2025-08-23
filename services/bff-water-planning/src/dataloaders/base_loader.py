from typing import List, Any, Dict, Optional
from aiodataloader import DataLoader
from db import DatabaseManager
from core import get_logger

logger = get_logger(__name__)


class BaseDataLoader(DataLoader):
    """Base class for all DataLoaders with common functionality"""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(batch_load_fn=self.batch_load_fn)
        self.db = db_manager
        self.logger = logger.bind(loader=self.__class__.__name__)
    
    async def batch_load_fn(self, keys: List[str]) -> List[Optional[Any]]:
        """Must be implemented by subclasses"""
        raise NotImplementedError
    
    def _map_results_to_keys(
        self, 
        keys: List[str], 
        results: List[Dict], 
        key_field: str = "id"
    ) -> List[Optional[Dict]]:
        """
        Map database results back to requested keys in order
        
        Args:
            keys: List of requested keys
            results: List of database results
            key_field: Field name to use as key
            
        Returns:
            List of results in same order as keys
        """
        result_map = {str(r[key_field]): r for r in results}
        return [result_map.get(str(key)) for key in keys]