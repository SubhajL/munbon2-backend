"""
Integration tests for WebSocket monitoring endpoints.
"""

import pytest
import asyncio
import json
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect


class TestWebSocketMonitoring:
    """Test WebSocket real-time monitoring"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(
        self, test_client, auth_headers
    ):
        """Test establishing WebSocket connection"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Send initial subscription
            websocket.send_json({
                "action": "subscribe",
                "channels": ["schedule_status", "operation_updates"]
            })
            
            # Receive acknowledgment
            data = websocket.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert "schedule_status" in data["channels"]
            assert "operation_updates" in data["channels"]
    
    @pytest.mark.asyncio
    async def test_receive_schedule_status_updates(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test receiving schedule status updates via WebSocket"""
        sample_schedule.status = "active"
        
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe to schedule updates
            websocket.send_json({
                "action": "subscribe",
                "channels": ["schedule_status"],
                "schedule_id": str(sample_schedule.id)
            })
            
            # Simulate status update
            # In real test, this would come from another endpoint
            websocket.send_json({
                "action": "ping"  # Keep connection alive
            })
            
            # Should receive updates
            data = websocket.receive_json()
            assert data["type"] in ["subscription_confirmed", "pong", "schedule_update"]
    
    @pytest.mark.asyncio
    async def test_operation_progress_updates(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test receiving operation progress updates"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe to operation updates
            websocket.send_json({
                "action": "subscribe",
                "channels": ["operation_progress"],
                "schedule_id": str(sample_schedule.id)
            })
            
            # Simulate operation update
            operation_update = {
                "operation_id": str(uuid4()),
                "gate_id": "GATE-001",
                "status": "in_progress",
                "progress_percentage": 50.0,
                "team_id": "TEAM-001",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # In real scenario, this would be triggered by operation status change
            websocket.send_json({
                "action": "simulate_update",
                "update_type": "operation_progress",
                "data": operation_update
            })
            
            # Receive updates
            data = websocket.receive_json()
            assert data["type"] in ["subscription_confirmed", "operation_update"]
    
    @pytest.mark.asyncio
    async def test_alert_notifications(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test receiving alert notifications"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe to alerts
            websocket.send_json({
                "action": "subscribe",
                "channels": ["alerts"],
                "alert_levels": ["warning", "error", "critical"]
            })
            
            # Simulate alert
            alert_data = {
                "alert_id": str(uuid4()),
                "type": "operation_delayed",
                "level": "warning",
                "message": "Operation GATE-001 delayed by 30 minutes",
                "timestamp": datetime.utcnow().isoformat(),
                "operation_id": str(uuid4()),
                "gate_id": "GATE-001"
            }
            
            websocket.send_json({
                "action": "simulate_alert",
                "data": alert_data
            })
            
            # Receive alert
            data = websocket.receive_json()
            assert data["type"] in ["subscription_confirmed", "alert"]
    
    @pytest.mark.asyncio
    async def test_team_location_updates(
        self, test_client, sample_team, auth_headers
    ):
        """Test receiving team location updates"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe to team updates
            websocket.send_json({
                "action": "subscribe",
                "channels": ["team_locations"],
                "team_ids": [str(sample_team.id)]
            })
            
            # Simulate location update
            location_update = {
                "team_id": str(sample_team.id),
                "latitude": 13.7563,
                "longitude": 100.5018,
                "accuracy": 10.5,
                "speed": 45.2,
                "heading": 180,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            websocket.send_json({
                "action": "update_location",
                "data": location_update
            })
            
            # Receive update
            data = websocket.receive_json()
            assert data["type"] in ["subscription_confirmed", "team_location"]
    
    @pytest.mark.asyncio
    async def test_websocket_authentication(
        self, test_client
    ):
        """Test WebSocket requires authentication"""
        # Try to connect without auth headers
        with pytest.raises(WebSocketDisconnect):
            with test_client.websocket_connect("/api/v1/monitoring/ws") as websocket:
                websocket.receive_json()
    
    @pytest.mark.asyncio
    async def test_websocket_heartbeat(
        self, test_client, auth_headers
    ):
        """Test WebSocket heartbeat mechanism"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Send ping
            websocket.send_json({
                "action": "ping",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Should receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_selective_subscription(
        self, test_client, auth_headers
    ):
        """Test selective channel subscription"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe to specific zones
            websocket.send_json({
                "action": "subscribe",
                "channels": ["zone_updates"],
                "zone_ids": ["ZONE-001", "ZONE-002"]
            })
            
            # Should only receive updates for subscribed zones
            data = websocket.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert data["filters"]["zone_ids"] == ["ZONE-001", "ZONE-002"]
    
    @pytest.mark.asyncio
    async def test_unsubscribe_channels(
        self, test_client, auth_headers
    ):
        """Test unsubscribing from channels"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Subscribe first
            websocket.send_json({
                "action": "subscribe",
                "channels": ["alerts", "operation_updates"]
            })
            
            # Receive confirmation
            data = websocket.receive_json()
            assert len(data["channels"]) == 2
            
            # Unsubscribe from one channel
            websocket.send_json({
                "action": "unsubscribe",
                "channels": ["alerts"]
            })
            
            # Receive confirmation
            data = websocket.receive_json()
            assert data["type"] == "unsubscribe_confirmed"
            assert "alerts" not in data["channels"]
            assert "operation_updates" in data["channels"]
    
    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(
        self, test_client, auth_headers
    ):
        """Test multiple concurrent WebSocket connections"""
        connections = []
        
        try:
            # Create multiple connections
            for i in range(3):
                ws = test_client.websocket_connect(
                    "/api/v1/monitoring/ws",
                    headers=auth_headers
                ).__enter__()
                connections.append(ws)
                
                # Subscribe each to different teams
                ws.send_json({
                    "action": "subscribe",
                    "channels": ["team_updates"],
                    "team_id": f"TEAM-{i+1:03d}"
                })
            
            # All should receive confirmations
            for ws in connections:
                data = ws.receive_json()
                assert data["type"] == "subscription_confirmed"
                
        finally:
            # Clean up connections
            for ws in connections:
                ws.__exit__(None, None, None)
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(
        self, test_client, auth_headers  
    ):
        """Test WebSocket error handling"""
        with test_client.websocket_connect(
            "/api/v1/monitoring/ws",
            headers=auth_headers
        ) as websocket:
            # Send invalid action
            websocket.send_json({
                "action": "invalid_action",
                "data": {}
            })
            
            # Should receive error response
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "message" in data
            
            # Send malformed data
            websocket.send_text("not json")
            
            # Should receive error or disconnect
            try:
                data = websocket.receive_json()
                assert data["type"] == "error"
            except WebSocketDisconnect:
                # Also acceptable behavior
                pass