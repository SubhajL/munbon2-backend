from typing import Dict, Optional
from dataclasses import dataclass
from dataloaders import (
    SectionLoader,
    PlotLoader,
    DemandLoader,
    AWDStatusLoader
)
from db import DatabaseManager
from core import get_logger

logger = get_logger(__name__)


@dataclass
class DataLoaders:
    """Container for all DataLoader instances"""
    section_loader: SectionLoader
    plot_loader: PlotLoader
    demand_loader: DemandLoader
    awd_loader: AWDStatusLoader


@dataclass 
class GraphQLContext:
    """Context object passed to all GraphQL resolvers"""
    db: DatabaseManager
    dataloaders: DataLoaders
    client_type: str = "web"  # web, mobile, api
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


async def build_context(
    request: Optional[Dict] = None,
    db_manager: Optional[DatabaseManager] = None
) -> GraphQLContext:
    """
    Build GraphQL context with DataLoaders and request info
    
    Args:
        request: HTTP request object
        db_manager: Database manager instance
        
    Returns:
        GraphQL context object
    """
    # Use provided db_manager or create new one
    db = db_manager or DatabaseManager()
    
    # Create DataLoader instances
    dataloaders = DataLoaders(
        section_loader=SectionLoader(db),
        plot_loader=PlotLoader(db),
        demand_loader=DemandLoader(db),
        awd_loader=AWDStatusLoader(db)
    )
    
    # Extract client info from request
    client_type = "web"
    user_agent = None
    request_id = None
    
    if request:
        headers = request.get("headers", {})
        user_agent = headers.get("user-agent", "")
        request_id = headers.get("x-request-id")
        
        # Determine client type from user agent
        if "mobile" in user_agent.lower():
            client_type = "mobile"
        elif "api" in user_agent.lower() or "curl" in user_agent.lower():
            client_type = "api"
    
    logger.info(
        "Building GraphQL context",
        client_type=client_type,
        request_id=request_id
    )
    
    return GraphQLContext(
        db=db,
        dataloaders=dataloaders,
        client_type=client_type,
        user_agent=user_agent,
        request_id=request_id
    )


async def cleanup_context(context: GraphQLContext):
    """
    Cleanup context resources
    
    Args:
        context: GraphQL context to cleanup
    """
    # Close AWD HTTP client
    if context.dataloaders.awd_loader:
        await context.dataloaders.awd_loader.close()
    
    logger.info("GraphQL context cleaned up", request_id=context.request_id)