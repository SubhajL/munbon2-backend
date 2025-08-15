from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time, timedelta
import json
from io import BytesIO
import base64

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus.flowables import KeepTogether

from ..core.logger import get_logger
from ..models.schedule import ScheduledOperation, FieldInstruction

logger = get_logger(__name__)


class FieldInstructionGenerator:
    """Generate human-readable instructions for field teams"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
    async def generate_team_instructions(
        self,
        schedule_id: str,
        team_id: str,
        operations: List[ScheduledOperation],
        route_info: Dict[str, Any],
        team_info: Dict[str, Any]
    ) -> FieldInstruction:
        """Generate complete instruction set for a team"""
        
        logger.info(f"Generating instructions for team {team_id}")
        
        # Sort operations by sequence
        sorted_ops = sorted(operations, key=lambda x: x.operation_sequence)
        
        # Generate components
        general_instructions = self._generate_general_instructions(team_info, len(sorted_ops))
        safety_notes = self._generate_safety_notes(sorted_ops)
        equipment_list = self._generate_equipment_list(sorted_ops)
        waypoints = self._generate_waypoints(sorted_ops, route_info)
        
        # Create instruction record
        instruction = FieldInstruction(
            schedule_id=schedule_id,
            team_id=team_id,
            team_name=team_info.get("team_name", team_id),
            operation_date=sorted_ops[0].operation_date if sorted_ops else datetime.now().date(),
            start_location=self._format_location(team_info.get("base_location")),
            end_location=self._format_location(team_info.get("base_location")),
            total_distance_km=route_info.get("total_distance_km", 0),
            estimated_duration_hours=route_info.get("total_duration_minutes", 0) / 60,
            total_operations=len(sorted_ops),
            operation_ids=[op.id for op in sorted_ops],
            route_coordinates=route_info.get("route_geometry"),
            waypoints=waypoints,
            general_instructions=general_instructions,
            safety_notes=safety_notes,
            special_equipment=equipment_list,
            supervisor_name=team_info.get("supervisor_name", ""),
            supervisor_phone=team_info.get("supervisor_phone", ""),
            emergency_contact="Emergency Services: 191",
        )
        
        return instruction
    
    def generate_operation_checklist(self, operation: ScheduledOperation) -> Dict[str, Any]:
        """Generate detailed checklist for a single operation"""
        
        checklist = {
            "gate_id": operation.gate_id,
            "gate_name": operation.gate_name or operation.gate_id,
            "location": {
                "latitude": operation.latitude,
                "longitude": operation.longitude,
                "description": operation.location_description or "See map for location"
            },
            "timing": {
                "arrival": operation.planned_start_time.strftime("%H:%M"),
                "departure": operation.planned_end_time.strftime("%H:%M"),
                "duration": f"{operation.duration_minutes} minutes"
            },
            "steps": self._generate_operation_steps(operation),
            "verification": self._generate_verification_steps(operation),
            "visual_guide": self._generate_visual_guide(operation),
        }
        
        return checklist
    
    def _generate_operation_steps(self, operation: ScheduledOperation) -> List[Dict[str, Any]]:
        """Generate step-by-step instructions for gate operation"""
        
        steps = []
        
        # Arrival
        steps.append({
            "step": 1,
            "action": "Arrive at gate location",
            "details": f"GPS: {operation.latitude}, {operation.longitude}",
            "check": False
        })
        
        # Safety check
        steps.append({
            "step": 2,
            "action": "Perform safety check",
            "details": "Ensure area is clear and safe to operate",
            "check": False
        })
        
        # Photo before
        steps.append({
            "step": 3,
            "action": "Take 'before' photo",
            "details": "Include gate position indicator in frame",
            "check": False
        })
        
        # Record current position
        steps.append({
            "step": 4,
            "action": "Record current gate position",
            "details": f"Expected: {operation.current_opening_percent or 0}%",
            "check": False
        })
        
        # Adjust gate
        adjustment = self._calculate_adjustment(
            operation.current_opening_percent or 0,
            operation.target_opening_percent
        )
        
        steps.append({
            "step": 5,
            "action": f"Adjust gate to {operation.target_opening_percent}%",
            "details": adjustment["instruction"],
            "check": False
        })
        
        # Wait for stabilization
        steps.append({
            "step": 6,
            "action": "Wait for flow stabilization",
            "details": "Allow 5 minutes for water flow to stabilize",
            "check": False
        })
        
        # Verify flow
        if operation.expected_flow_after:
            steps.append({
                "step": 7,
                "action": "Verify downstream flow",
                "details": f"Expected flow: {operation.expected_flow_after:.2f} m³/s",
                "check": False
            })
        
        # Photo after
        steps.append({
            "step": 8,
            "action": "Take 'after' photo",
            "details": "Show new gate position clearly",
            "check": False
        })
        
        # Record completion
        steps.append({
            "step": 9,
            "action": "Record actual position and observations",
            "details": "Note any issues or deviations",
            "check": False
        })
        
        return steps
    
    def _calculate_adjustment(self, current: float, target: float) -> Dict[str, Any]:
        """Calculate gate adjustment instructions"""
        
        difference = target - current
        
        # Assume 10% = 1 full turn of wheel
        turns = abs(difference) / 10.0
        direction = "CLOCKWISE" if difference > 0 else "COUNTER-CLOCKWISE"
        
        instruction = f"Turn wheel {direction} {turns:.1f} turns"
        
        if turns < 0.1:
            instruction = "Gate is already at target position"
        elif turns > 10:
            instruction += " (CAUTION: Large adjustment - proceed slowly)"
        
        return {
            "instruction": instruction,
            "turns": turns,
            "direction": direction,
            "current_percent": current,
            "target_percent": target,
            "change_percent": difference
        }
    
    def _generate_verification_steps(self, operation: ScheduledOperation) -> List[str]:
        """Generate verification checklist"""
        
        return [
            "Gate moves freely without obstruction",
            "No visible leaks or damage",
            "Position indicator matches actual position",
            "Downstream flow appears normal",
            "No unusual sounds or vibrations",
        ]
    
    def _generate_visual_guide(self, operation: ScheduledOperation) -> Dict[str, Any]:
        """Generate visual guide for gate positioning"""
        
        # This would generate actual diagrams in production
        # For now, return descriptive guide
        
        current = operation.current_opening_percent or 0
        target = operation.target_opening_percent
        
        guide = {
            "type": "gate_position_diagram",
            "current_position": {
                "percent": current,
                "description": self._describe_gate_position(current),
                "visual_marker": "RED"
            },
            "target_position": {
                "percent": target,
                "description": self._describe_gate_position(target),
                "visual_marker": "GREEN"
            },
            "adjustment_required": {
                "direction": "increase" if target > current else "decrease",
                "amount": abs(target - current),
                "turns": abs(target - current) / 10.0
            }
        }
        
        return guide
    
    def _describe_gate_position(self, percent: float) -> str:
        """Describe gate position in words"""
        
        if percent == 0:
            return "Fully closed"
        elif percent == 100:
            return "Fully open"
        elif percent < 25:
            return "Nearly closed"
        elif percent < 50:
            return "One-quarter open"
        elif percent < 75:
            return "Half open"
        else:
            return "Nearly fully open"
    
    def generate_printable_instructions(
        self,
        team_id: str,
        date: datetime,
        operations: List[Dict],
        route_info: Dict
    ) -> bytes:
        """Generate PDF instructions for printing"""
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Title
        title = Paragraph(
            f"Field Instructions - Team {team_id}<br/>{date.strftime('%A, %B %d, %Y')}",
            self.styles['Title']
        )
        story.append(title)
        story.append(Spacer(1, 0.5 * inch))
        
        # Summary
        summary_data = [
            ["Total Operations:", str(len(operations))],
            ["Estimated Duration:", f"{route_info['total_duration_minutes']:.0f} minutes"],
            ["Total Distance:", f"{route_info['total_distance_km']:.1f} km"],
            ["Start Time:", "07:00"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5 * inch))
        
        # Operations list
        story.append(Paragraph("Operations Schedule", self.styles['Heading2']))
        
        for i, op in enumerate(operations):
            # Operation header
            op_title = Paragraph(
                f"{i+1}. {op['gate_name']} ({op['gate_id']})",
                self.styles['Heading3']
            )
            
            # Operation details
            op_data = [
                ["Arrival Time:", op['arrival_time']],
                ["GPS Location:", f"{op['latitude']:.6f}, {op['longitude']:.6f}"],
                ["Current Position:", f"{op['current_opening']:.0f}%"],
                ["Target Position:", f"{op['target_opening']:.0f}%"],
                ["Action Required:", op['adjustment']['instruction']],
            ]
            
            op_table = Table(op_data, colWidths=[1.5*inch, 4*inch])
            op_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightyellow),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            # Keep operation together
            operation_block = KeepTogether([
                op_title,
                op_table,
                Spacer(1, 0.25 * inch)
            ])
            
            story.append(operation_block)
        
        # Emergency contacts
        story.append(PageBreak())
        story.append(Paragraph("Emergency Contacts", self.styles['Heading2']))
        
        emergency_data = [
            ["Supervisor:", route_info.get('supervisor_name', 'N/A'), 
             route_info.get('supervisor_phone', 'N/A')],
            ["Control Center:", "24/7 Operations", "02-123-4567"],
            ["Emergency Services:", "Police/Fire/Medical", "191"],
        ]
        
        emergency_table = Table(emergency_data, colWidths=[1.5*inch, 2*inch, 1.5*inch])
        emergency_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.red),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(emergency_table)
        
        # Build PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
    
    def generate_mobile_instructions(
        self,
        team_id: str,
        operations: List[Dict],
        route_info: Dict
    ) -> Dict[str, Any]:
        """Generate mobile-friendly JSON instructions"""
        
        mobile_data = {
            "version": "1.0",
            "team_id": team_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_operations": len(operations),
                "estimated_duration_minutes": route_info["total_duration_minutes"],
                "total_distance_km": route_info["total_distance_km"],
                "start_time": "07:00",
                "end_time": self._calculate_end_time(
                    "07:00", 
                    route_info["total_duration_minutes"]
                ),
            },
            "route": route_info.get("route_geometry"),
            "operations": [],
            "offline_maps": self._generate_offline_map_tiles(operations),
            "emergency": {
                "supervisor": {
                    "name": route_info.get("supervisor_name", ""),
                    "phone": route_info.get("supervisor_phone", ""),
                },
                "control_center": {
                    "name": "24/7 Operations",
                    "phone": "02-123-4567",
                },
                "emergency_services": "191"
            }
        }
        
        # Add detailed operations
        for i, op in enumerate(operations):
            mobile_op = {
                "sequence": i + 1,
                "gate": {
                    "id": op["gate_id"],
                    "name": op["gate_name"],
                    "type": op.get("gate_type", "slide"),
                },
                "location": {
                    "latitude": op["latitude"],
                    "longitude": op["longitude"],
                    "description": op.get("location_description", ""),
                    "navigation_notes": op.get("navigation_notes", ""),
                },
                "timing": {
                    "arrival": op["arrival_time"],
                    "duration": op.get("duration_minutes", 15),
                },
                "operation": {
                    "current_position": op["current_opening"],
                    "target_position": op["target_opening"],
                    "adjustment": op["adjustment"],
                    "expected_flow": op.get("expected_flow", 0),
                },
                "checklist": self._generate_mobile_checklist(op),
                "photos_required": ["before", "after", "position_indicator"],
                "offline_data": {
                    "gate_photo": op.get("gate_photo_base64", ""),
                    "location_photo": op.get("location_photo_base64", ""),
                }
            }
            
            mobile_data["operations"].append(mobile_op)
        
        return mobile_data
    
    def _generate_mobile_checklist(self, operation: Dict) -> List[Dict]:
        """Generate mobile-friendly checklist"""
        
        checklist = []
        steps = [
            "Arrive at location",
            "Safety check",
            "Take before photo",
            "Record current position",
            f"Adjust to {operation['target_opening']}%",
            "Wait for stabilization",
            "Verify flow",
            "Take after photo",
            "Complete notes"
        ]
        
        for i, step in enumerate(steps):
            checklist.append({
                "id": f"step_{i+1}",
                "description": step,
                "completed": False,
                "timestamp": None,
                "required": True
            })
        
        return checklist
    
    def _generate_offline_map_tiles(self, operations: List[Dict]) -> Dict[str, str]:
        """Generate offline map tile references"""
        
        # In production, this would generate actual map tiles
        # For now, return tile server URLs
        
        bounds = self._calculate_bounds(operations)
        
        return {
            "tile_server": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "bounds": bounds,
            "zoom_levels": [12, 13, 14, 15, 16],
            "cache_size_mb": 50
        }
    
    def _calculate_bounds(self, operations: List[Dict]) -> Dict[str, float]:
        """Calculate geographic bounds for operations"""
        
        if not operations:
            return {"north": 0, "south": 0, "east": 0, "west": 0}
        
        lats = [op["latitude"] for op in operations]
        lons = [op["longitude"] for op in operations]
        
        return {
            "north": max(lats) + 0.01,  # Add padding
            "south": min(lats) - 0.01,
            "east": max(lons) + 0.01,
            "west": min(lons) - 0.01,
        }
    
    def _calculate_end_time(self, start_time: str, duration_minutes: float) -> str:
        """Calculate end time from start time and duration"""
        
        start = datetime.strptime(start_time, "%H:%M")
        end = start + timedelta(minutes=duration_minutes)
        return end.strftime("%H:%M")
    
    def _generate_general_instructions(self, team_info: Dict, operation_count: int) -> str:
        """Generate general instructions text"""
        
        return f"""
Field Operations Instructions

Team: {team_info.get('team_name', 'Field Team')}
Date: {datetime.now().strftime('%B %d, %Y')}
Total Operations: {operation_count}

General Guidelines:
1. Start operations at designated time
2. Follow the optimized route for efficiency
3. Complete all safety checks before operating gates
4. Take clear photos for verification
5. Record any deviations or issues
6. Contact supervisor if problems arise
7. Ensure all gates are properly secured after adjustment

Remember: Safety first. If conditions seem unsafe, stop and contact supervisor.
"""
    
    def _generate_safety_notes(self, operations: List[ScheduledOperation]) -> str:
        """Generate safety notes based on operations"""
        
        notes = [
            "Always wear safety equipment (hard hat, safety vest, gloves)",
            "Check for wildlife or obstacles before approaching gates",
            "Be aware of slippery surfaces near water",
            "Never operate damaged equipment",
            "Maintain communication with team members",
        ]
        
        # Add specific notes based on operations
        if any(op.target_opening_percent > 80 for op in operations):
            notes.append("CAUTION: High flow operations - extra care required")
        
        if any(op.canal_name and "main" in op.canal_name.lower() for op in operations):
            notes.append("Working on main canal - follow main canal safety protocol")
        
        return "\n".join(f"• {note}" for note in notes)
    
    def _generate_equipment_list(self, operations: List[ScheduledOperation]) -> List[str]:
        """Generate required equipment list"""
        
        standard_equipment = [
            "Gate operation tools",
            "Safety equipment (PPE)",
            "Mobile device with app",
            "Backup printed instructions",
            "Camera/phone for photos",
            "Measuring tape",
            "Notepad and pen",
            "First aid kit",
            "Flashlight",
            "Two-way radio",
        ]
        
        # Add special equipment based on operations
        special = set()
        for op in operations:
            if op.gate_id and "M(0" in op.gate_id:  # Main gates
                special.add("Heavy-duty gate wrench")
            if op.target_opening_percent == 0:  # Closing operations
                special.add("Lock and chain")
        
        return standard_equipment + list(special)
    
    def _generate_waypoints(self, operations: List[ScheduledOperation], route_info: Dict) -> List[Dict]:
        """Generate waypoints for navigation"""
        
        waypoints = []
        
        for i, op in enumerate(operations):
            waypoint = {
                "sequence": i + 1,
                "type": "gate_operation",
                "gate_id": op.gate_id,
                "gate_name": op.gate_name,
                "coordinates": [op.longitude, op.latitude],
                "arrival_time": op.planned_start_time.isoformat(),
                "duration_minutes": op.duration_minutes,
                "navigation_notes": self._generate_navigation_notes(op, i, operations),
            }
            waypoints.append(waypoint)
        
        return waypoints
    
    def _generate_navigation_notes(
        self,
        operation: ScheduledOperation,
        index: int,
        all_operations: List[ScheduledOperation]
    ) -> str:
        """Generate navigation notes for a waypoint"""
        
        notes = []
        
        # Add landmark info if available
        if operation.location_description:
            notes.append(operation.location_description)
        
        # Add relative directions
        if index > 0:
            prev_op = all_operations[index - 1]
            direction = self._calculate_direction(
                (prev_op.latitude, prev_op.longitude),
                (operation.latitude, operation.longitude)
            )
            distance = self._calculate_distance(
                (prev_op.latitude, prev_op.longitude),
                (operation.latitude, operation.longitude)
            )
            notes.append(f"{distance:.1f} km {direction} from previous gate")
        
        return " | ".join(notes)
    
    def _calculate_direction(self, from_loc: Tuple[float, float], to_loc: Tuple[float, float]) -> str:
        """Calculate cardinal direction between two points"""
        
        lat1, lon1 = from_loc
        lat2, lon2 = to_loc
        
        # Simple cardinal direction
        lat_diff = lat2 - lat1
        lon_diff = lon2 - lon1
        
        if abs(lat_diff) > abs(lon_diff):
            return "North" if lat_diff > 0 else "South"
        else:
            return "East" if lon_diff > 0 else "West"
    
    def _calculate_distance(self, from_loc: Tuple[float, float], to_loc: Tuple[float, float]) -> float:
        """Calculate distance between two points in km"""
        
        # Simplified calculation
        lat1, lon1 = from_loc
        lat2, lon2 = to_loc
        
        lat_diff = abs(lat2 - lat1)
        lon_diff = abs(lon2 - lon1)
        
        # Rough approximation
        distance = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111
        
        return distance
    
    def _format_location(self, location: Optional[Dict]) -> str:
        """Format location for display"""
        
        if not location:
            return "Base Station"
        
        if isinstance(location, dict):
            return f"{location.get('name', 'Location')} ({location.get('lat', 0):.4f}, {location.get('lng', 0):.4f})"
        
        return str(location)