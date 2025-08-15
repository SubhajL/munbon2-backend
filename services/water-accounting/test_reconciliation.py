#!/usr/bin/env python3
"""
Demonstrate Weekly Reconciliation Workflow
"""

import json
from datetime import datetime, timedelta
import random

class ReconciliationDemo:
    """Demonstrate reconciliation between automated and manual gates"""
    
    def __init__(self):
        self.automated_gates = [f"GATE-{i:03d}" for i in range(1, 21)]  # 20 automated gates
        self.manual_gates = [f"GATE-M{i:03d}" for i in range(1, 31)]  # 30 manual gates
    
    def generate_delivery_data(self, week_number, year):
        """Generate sample delivery data for a week"""
        deliveries = []
        
        # Automated gate deliveries (high confidence)
        for gate_id in self.automated_gates:
            for _ in range(random.randint(2, 4)):  # 2-4 deliveries per gate
                delivery = {
                    "delivery_id": f"DEL-{gate_id}-W{week_number}-{random.randint(1000, 9999)}",
                    "gate_id": gate_id,
                    "gate_type": "automated",
                    "gate_outflow_m3": random.uniform(4000, 6000),
                    "section_inflow_m3": 0,  # Will calculate
                    "transit_loss_m3": 0,    # Will calculate
                    "confidence_level": 0.95
                }
                # Calculate losses (2-5% for automated gates)
                loss_percent = random.uniform(0.02, 0.05)
                delivery["transit_loss_m3"] = delivery["gate_outflow_m3"] * loss_percent
                delivery["section_inflow_m3"] = delivery["gate_outflow_m3"] - delivery["transit_loss_m3"]
                deliveries.append(delivery)
        
        # Manual gate deliveries (lower confidence)
        for gate_id in self.manual_gates:
            for _ in range(random.randint(1, 3)):  # 1-3 deliveries per gate
                # Estimate based on gate opening
                opening_hours = random.uniform(2, 8)
                opening_percent = random.uniform(50, 100)
                head_difference = random.uniform(0.5, 2.0)
                
                # Simple flow estimation
                estimated_flow = 0.6 * 2.0 * (opening_percent/100) * (2 * 9.81 * head_difference) ** 0.5
                estimated_volume = estimated_flow * opening_hours * 3600
                
                delivery = {
                    "delivery_id": f"DEL-{gate_id}-W{week_number}-{random.randint(1000, 9999)}",
                    "gate_id": gate_id,
                    "gate_type": "manual",
                    "gate_outflow_m3": estimated_volume,
                    "section_inflow_m3": 0,
                    "transit_loss_m3": 0,
                    "confidence_level": 0.70,
                    "estimation_params": {
                        "opening_hours": opening_hours,
                        "opening_percent": opening_percent,
                        "head_difference_m": head_difference
                    }
                }
                # Higher losses for manual gates (3-8%)
                loss_percent = random.uniform(0.03, 0.08)
                delivery["transit_loss_m3"] = delivery["gate_outflow_m3"] * loss_percent
                delivery["section_inflow_m3"] = delivery["gate_outflow_m3"] - delivery["transit_loss_m3"]
                deliveries.append(delivery)
        
        return deliveries
    
    def calculate_reconciliation(self, deliveries):
        """Calculate reconciliation between automated and manual gates"""
        
        # Separate by gate type
        automated = [d for d in deliveries if d["gate_type"] == "automated"]
        manual = [d for d in deliveries if d["gate_type"] == "manual"]
        
        # Calculate totals
        auto_outflow = sum(d["gate_outflow_m3"] for d in automated)
        auto_inflow = sum(d["section_inflow_m3"] for d in automated)
        auto_losses = sum(d["transit_loss_m3"] for d in automated)
        
        manual_outflow = sum(d["gate_outflow_m3"] for d in manual)
        manual_inflow = sum(d["section_inflow_m3"] for d in manual)
        manual_losses = sum(d["transit_loss_m3"] for d in manual)
        
        total_outflow = auto_outflow + manual_outflow
        total_inflow = auto_inflow + manual_inflow
        total_losses = auto_losses + manual_losses
        
        # Check water balance
        expected_losses = total_outflow - total_inflow
        discrepancy = expected_losses - total_losses
        discrepancy_percent = (discrepancy / total_outflow * 100) if total_outflow > 0 else 0
        
        return {
            "automated": {
                "count": len(automated),
                "total_outflow_m3": round(auto_outflow, 2),
                "total_inflow_m3": round(auto_inflow, 2),
                "total_losses_m3": round(auto_losses, 2),
                "avg_loss_percent": round((auto_losses / auto_outflow * 100) if auto_outflow > 0 else 0, 2)
            },
            "manual": {
                "count": len(manual),
                "total_outflow_m3": round(manual_outflow, 2),
                "total_inflow_m3": round(manual_inflow, 2),
                "total_losses_m3": round(manual_losses, 2),
                "avg_loss_percent": round((manual_losses / manual_outflow * 100) if manual_outflow > 0 else 0, 2)
            },
            "system_total": {
                "total_outflow_m3": round(total_outflow, 2),
                "total_inflow_m3": round(total_inflow, 2),
                "total_losses_m3": round(total_losses, 2),
                "expected_losses_m3": round(expected_losses, 2),
                "discrepancy_m3": round(discrepancy, 2),
                "discrepancy_percent": round(discrepancy_percent, 2),
                "needs_adjustment": abs(discrepancy_percent) > 5
            }
        }
    
    def apply_adjustments(self, deliveries, reconciliation_data):
        """Apply proportional adjustments to manual gate estimates"""
        
        if not reconciliation_data["system_total"]["needs_adjustment"]:
            return []
        
        adjustments = []
        discrepancy = reconciliation_data["system_total"]["discrepancy_m3"]
        manual_total = reconciliation_data["manual"]["total_outflow_m3"]
        
        # Get manual deliveries
        manual_deliveries = [d for d in deliveries if d["gate_type"] == "manual"]
        
        for delivery in manual_deliveries:
            # Calculate proportional adjustment
            proportion = delivery["gate_outflow_m3"] / manual_total
            adjustment_m3 = discrepancy * proportion
            
            # Create adjustment record
            adjustment = {
                "delivery_id": delivery["delivery_id"],
                "gate_id": delivery["gate_id"],
                "original_outflow_m3": delivery["gate_outflow_m3"],
                "adjustment_m3": round(adjustment_m3, 2),
                "adjustment_percent": round((adjustment_m3 / delivery["gate_outflow_m3"] * 100), 2),
                "adjusted_outflow_m3": round(delivery["gate_outflow_m3"] + adjustment_m3, 2),
                "confidence_before": delivery["confidence_level"],
                "confidence_after": 0.85  # Improved after reconciliation
            }
            adjustments.append(adjustment)
        
        return adjustments
    
    def generate_report(self, week_number, year, reconciliation_data, adjustments):
        """Generate reconciliation report"""
        
        report = {
            "reconciliation_id": f"REC-{year}-W{week_number:02d}",
            "week": week_number,
            "year": year,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "automated_deliveries": reconciliation_data["automated"]["count"],
                "manual_deliveries": reconciliation_data["manual"]["count"],
                "total_water_delivered_m3": reconciliation_data["system_total"]["total_outflow_m3"],
                "discrepancy_found": reconciliation_data["system_total"]["needs_adjustment"],
                "discrepancy_m3": reconciliation_data["system_total"]["discrepancy_m3"],
                "discrepancy_percent": reconciliation_data["system_total"]["discrepancy_percent"]
            },
            "automated_gates": {
                "performance": "Excellent",
                "total_volume_m3": reconciliation_data["automated"]["total_outflow_m3"],
                "avg_loss_percent": reconciliation_data["automated"]["avg_loss_percent"],
                "confidence_level": 0.95
            },
            "manual_gates": {
                "performance": "Good" if not adjustments else "Fair",
                "total_volume_m3": reconciliation_data["manual"]["total_outflow_m3"],
                "avg_loss_percent": reconciliation_data["manual"]["avg_loss_percent"],
                "confidence_level": 0.70,
                "adjustments_made": len(adjustments)
            },
            "recommendations": []
        }
        
        # Add recommendations
        if abs(reconciliation_data["system_total"]["discrepancy_percent"]) > 10:
            report["recommendations"].append(
                "High discrepancy detected. Consider installing flow meters at high-volume manual gates."
            )
        
        if reconciliation_data["manual"]["avg_loss_percent"] > 6:
            report["recommendations"].append(
                "Manual gates showing high losses. Review canal maintenance schedule."
            )
        
        if len(adjustments) > 20:
            report["recommendations"].append(
                "Many manual gates required adjustment. Increase frequency of manual measurements."
            )
        
        return report

def main():
    """Run reconciliation demonstration"""
    print("=" * 70)
    print("Water Accounting Service - Weekly Reconciliation Demonstration")
    print("=" * 70)
    
    demo = ReconciliationDemo()
    week = 45
    year = 2024
    
    print(f"\nGenerating data for Week {week}, {year}...")
    
    # Generate delivery data
    deliveries = demo.generate_delivery_data(week, year)
    print(f"- Generated {len(deliveries)} deliveries")
    print(f"  - Automated gates: {len([d for d in deliveries if d['gate_type'] == 'automated'])}")
    print(f"  - Manual gates: {len([d for d in deliveries if d['gate_type'] == 'manual'])}")
    
    # Calculate reconciliation
    print("\nCalculating reconciliation...")
    reconciliation = demo.calculate_reconciliation(deliveries)
    
    print("\nAutomated Gates Summary:")
    print(f"- Deliveries: {reconciliation['automated']['count']}")
    print(f"- Total outflow: {reconciliation['automated']['total_outflow_m3']:,.0f} m³")
    print(f"- Average loss: {reconciliation['automated']['avg_loss_percent']}%")
    
    print("\nManual Gates Summary:")
    print(f"- Deliveries: {reconciliation['manual']['count']}")
    print(f"- Total outflow: {reconciliation['manual']['total_outflow_m3']:,.0f} m³")
    print(f"- Average loss: {reconciliation['manual']['avg_loss_percent']}%")
    
    print("\nSystem Water Balance:")
    print(f"- Total outflow: {reconciliation['system_total']['total_outflow_m3']:,.0f} m³")
    print(f"- Total inflow: {reconciliation['system_total']['total_inflow_m3']:,.0f} m³")
    print(f"- Total losses: {reconciliation['system_total']['total_losses_m3']:,.0f} m³")
    print(f"- Discrepancy: {reconciliation['system_total']['discrepancy_m3']:,.0f} m³ ({reconciliation['system_total']['discrepancy_percent']}%)")
    
    # Apply adjustments if needed
    if reconciliation["system_total"]["needs_adjustment"]:
        print("\n⚠️  Discrepancy exceeds 5% threshold - adjustments required")
        adjustments = demo.apply_adjustments(deliveries, reconciliation)
        print(f"- Applied {len(adjustments)} adjustments to manual gate estimates")
        
        # Show sample adjustments
        print("\nSample Adjustments (first 5):")
        for adj in adjustments[:5]:
            print(f"  - {adj['gate_id']}: {adj['adjustment_m3']:+.0f} m³ ({adj['adjustment_percent']:+.1f}%)")
    else:
        print("\n✓ Water balance within acceptable limits - no adjustments needed")
        adjustments = []
    
    # Generate report
    print("\nGenerating reconciliation report...")
    report = demo.generate_report(week, year, reconciliation, adjustments)
    
    print("\n" + "=" * 70)
    print("RECONCILIATION REPORT")
    print("=" * 70)
    print(f"Report ID: {report['reconciliation_id']}")
    print(f"Period: Week {report['week']}, {report['year']}")
    print(f"\nSummary:")
    print(f"- Total deliveries: {report['summary']['automated_deliveries'] + report['summary']['manual_deliveries']}")
    print(f"- Total water delivered: {report['summary']['total_water_delivered_m3']:,.0f} m³")
    print(f"- Discrepancy: {report['summary']['discrepancy_m3']:,.0f} m³ ({report['summary']['discrepancy_percent']}%)")
    
    if report['recommendations']:
        print(f"\nRecommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
    
    print("\n" + "=" * 70)
    print("Reconciliation completed successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()