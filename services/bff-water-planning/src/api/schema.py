import strawberry
from starlette.background import BackgroundTasks
from strawberry.fastapi import GraphQLRouter
from datetime import datetime
from strawberry.scalars import JSON

# Import all query types
from .graphql_enhanced import Query as EnhancedQuery
from .aggregated_queries import AggregatedQueries
from .water_demand_queries import WaterDemandQueries
from .crop_season_queries import CropSeasonQueries

# Import mutations
from .graphql_schema import Mutation as BaseMutation
from .awd_mutations import AWDMutations
from .crop_season_mutations import CropSeasonMutations

# Import subscriptions
from .subscriptions import Subscription

# Import context builder
from context import build_context, cleanup_context, GraphQLContext


# Combine all queries
@strawberry.type
class Query(EnhancedQuery, AggregatedQueries):
    """Combined query type with all available queries"""
    
    # Add new query types as fields
    water_demands: WaterDemandQueries = strawberry.field(resolver=lambda: WaterDemandQueries())
    crop_season: CropSeasonQueries = strawberry.field(resolver=lambda: CropSeasonQueries())


# Combine all mutations
@strawberry.type
class Mutation(BaseMutation, AWDMutations):
    """Combined mutation type with all available mutations"""
    
    # Add new mutation types as fields
    crop_season: CropSeasonMutations = strawberry.field(resolver=lambda: CropSeasonMutations())
    
    @strawberry.mutation
    async def trigger_what_if_scenario(
        self,
        info: strawberry.Info[GraphQLContext],
        scenario_name: str,
        parameters: JSON
    ) -> JSON:
        """Trigger a what-if scenario calculation"""
        import uuid
        from api.subscriptions import publish_demand_update
        
        job_id = str(uuid.uuid4())
        
        # In production, would trigger background job
        # For now, return mock response
        return {
            "job_id": job_id,
            "status": "started",
            "message": f"What-if scenario '{scenario_name}' started",
            "subscribe_to": f"job:progress:{job_id}"
        }
    
    @strawberry.mutation
    async def override_demand_calculation(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str,
        override_value: float,
        reason: str,
        valid_until: datetime
    ) -> JSON:
        """Override automatic demand calculation with manual value"""
        # In production, would save to database
        return {
            "success": True,
            "section_id": section_id,
            "override_value": override_value,
            "reason": reason,
            "valid_until": valid_until,
            "created_by": "system",  # Would use actual user
            "created_at": datetime.utcnow()
        }


# Create the complete schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)


# Create GraphQL router with context
def create_graphql_app() -> GraphQLRouter:
    """Create GraphQL router with proper context injection"""
    
    async def get_context(request, response) -> GraphQLContext:
        """Build context for each request"""
        # Extract request info
        request_info = {
            "headers": dict(request.headers),
            "method": request.method,
            "url": str(request.url)
        }
        
        # Build context
        context = await build_context(request_info)
        
        # Store cleanup function
        request.state.graphql_context = context
        
        return context
    
    # Create router
    graphql_app = GraphQLRouter(
        schema,
        path="/graphql",
        context_getter=get_context,
        graphql_ide="graphiql",
    )

    return graphql_app


def register_graphql_context_cleanup(app):
    """Attach per-request GraphQL context cleanup to the FastAPI app.

    HTTP middleware cannot hang off an APIRouter (the old
    ``@graphql_app.router.middleware("http")`` form never existed on
    GraphQLRouter and made the service unbootable), so cleanup must be
    registered on the application itself. Cleanup runs as a response
    background task — after the final body chunk — so streamed GraphQL
    responses cannot lose their context mid-flight.
    """

    @app.middleware("http")
    async def cleanup_middleware(request, call_next):
        response = await call_next(request)

        context = getattr(request.state, "graphql_context", None)
        if context is not None:
            tasks = BackgroundTasks()
            if response.background is not None:
                tasks.add_task(response.background)
            tasks.add_task(cleanup_context, context)
            response.background = tasks

        return response


# Export for use in main.py
__all__ = ["schema", "create_graphql_app", "register_graphql_context_cleanup"]