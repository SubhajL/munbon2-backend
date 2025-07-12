#!/usr/bin/env python3
"""
Validate ROS calculations against Excel data
"""

import json
import math
from datetime import datetime

def load_excel_data():
    """Load extracted Excel data"""
    with open('excel_extracted_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_kc_data():
    """Load detailed Kc data"""
    with open('kc_detailed_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_etc(eto, kc):
    """Calculate ETc = ETo * Kc"""
    return eto * kc

def validate_eto_calculations(excel_data):
    """Validate ETo calculations"""
    print("=== ETo Validation ===")
    print(f"Station: {excel_data['eto_data']['station']}")
    print(f"Annual Average ETo: {excel_data['eto_data']['annual_average']:.2f} mm")
    print("\nMonthly ETo values (mm):")
    
    for month, value in excel_data['eto_data']['monthly_eto'].items():
        print(f"  {month}: {value:.2f}")
    
    # Calculate daily average for each month
    days_in_month = {
        'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30,
        'May': 31, 'Jun': 30, 'Jul': 31, 'Aug': 31,
        'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31
    }
    
    print("\nDaily Average ETo (mm/day):")
    for month, value in excel_data['eto_data']['monthly_eto'].items():
        daily_avg = value / days_in_month[month]
        print(f"  {month}: {daily_avg:.2f}")

def validate_kc_calculations(excel_data, kc_data):
    """Validate Kc calculations for key crops"""
    print("\n=== Kc Validation ===")
    
    # Focus on rice crops
    rice_crops = ['ข้าว กข.(นาดำ)', 'ข้าวขาวดอกมะลิ105']
    
    for crop in rice_crops:
        if crop in excel_data['kc_summary']:
            summary = excel_data['kc_summary'][crop]
            print(f"\n{crop}:")
            print(f"  Average Kc: {summary['average_kc']:.3f}")
            print(f"  Max Kc: {summary['max_kc']:.3f}")
            print(f"  Min Kc: {summary['min_kc']:.3f}")
            print(f"  Weeks with data: {summary['weeks_with_data']}")
            
            # Show growth stages based on Kc values
            if crop in kc_data:
                weekly_values = kc_data[crop]['weekly_values']
                print(f"\n  Growth stages (based on Kc values):")
                
                # Find non-zero weeks
                active_weeks = [(i+1, v) for i, v in enumerate(weekly_values) if v > 0]
                
                if active_weeks:
                    # Initial stage (low Kc)
                    initial_weeks = [(w, v) for w, v in active_weeks if v < 1.0]
                    if initial_weeks:
                        print(f"    Initial stage: Weeks {initial_weeks[0][0]}-{initial_weeks[-1][0]}, Kc={initial_weeks[0][1]:.2f}")
                    
                    # Development stage (increasing Kc)
                    dev_weeks = [(w, v) for w, v in active_weeks if 1.0 <= v < 1.2]
                    if dev_weeks:
                        print(f"    Development stage: Weeks {dev_weeks[0][0]}-{dev_weeks[-1][0]}, Kc={dev_weeks[0][1]:.2f}-{dev_weeks[-1][1]:.2f}")
                    
                    # Mid-season stage (high Kc)
                    mid_weeks = [(w, v) for w, v in active_weeks if v >= 1.2]
                    if mid_weeks:
                        print(f"    Mid-season stage: Weeks {mid_weeks[0][0]}-{mid_weeks[-1][0]}, Kc={mid_weeks[0][1]:.2f}-{mid_weeks[-1][1]:.2f}")

def calculate_water_requirements(excel_data, kc_data):
    """Calculate water requirements for validation"""
    print("\n=== Water Requirements Calculation ===")
    
    # Get monthly ETo for May (typical planting month)
    may_eto = excel_data['eto_data']['monthly_eto']['May']
    daily_eto = may_eto / 31  # May has 31 days
    
    print(f"\nMay ETo: {may_eto:.2f} mm/month ({daily_eto:.2f} mm/day)")
    
    # Calculate for rice
    rice_crop = 'ข้าว กข.(นาดำ)'
    if rice_crop in excel_data['kc_summary']:
        kc_avg = excel_data['kc_summary'][rice_crop]['average_kc']
        kc_max = excel_data['kc_summary'][rice_crop]['max_kc']
        
        etc_avg = daily_eto * kc_avg
        etc_max = daily_eto * kc_max
        
        print(f"\n{rice_crop} water requirements:")
        print(f"  Average ETc: {etc_avg:.2f} mm/day")
        print(f"  Maximum ETc: {etc_max:.2f} mm/day")
        
        # Weekly requirements
        print(f"  Weekly average: {etc_avg * 7:.2f} mm/week")
        print(f"  Weekly maximum: {etc_max * 7:.2f} mm/week")
        
        # Include seepage
        seepage = excel_data['parameters']['seepage_rate_mm_per_week']
        total_weekly = (etc_avg * 7) + seepage
        print(f"\n  Total weekly requirement (with seepage): {total_weekly:.2f} mm/week")
        
        # Area calculations
        area_rai = excel_data['parameters']['planting_areas'][0]['area_rai']
        print(f"\n  Area: {area_rai:.0f} rai")
        
        # Convert to cubic meters (1 rai = 1,600 m², 1 mm = 0.001 m)
        water_volume_m3 = total_weekly * 0.001 * area_rai * 1600
        print(f"  Weekly water volume: {water_volume_m3:,.0f} m³")
        print(f"  Daily water volume: {water_volume_m3/7:,.0f} m³")

def compare_with_ros_api():
    """Generate API calls to compare with ROS service"""
    print("\n=== ROS API Comparison ===")
    print("\nTo validate against the ROS service, make these API calls:")
    
    print("\n1. Get ETo for Nakhon Ratchasima:")
    print("   GET http://localhost:3007/api/eto/nakhon-ratchasima")
    
    print("\n2. Get Kc for rice:")
    print("   GET http://localhost:3007/api/kc/rice")
    
    print("\n3. Calculate ETc:")
    print("   POST http://localhost:3007/api/etc/calculate")
    print("   Body: {")
    print('     "location": "nakhon-ratchasima",')
    print('     "cropType": "rice",')
    print('     "plantingDate": "2025-05-01",')
    print('     "area": 45731')
    print("   }")
    
    print("\n4. Calculate water requirements:")
    print("   POST http://localhost:3007/api/water-requirements")
    print("   Body: {")
    print('     "cropType": "rice",')
    print('     "area": 45731,')
    print('     "location": "nakhon-ratchasima",')
    print('     "plantingDate": "2025-05-01",')
    print('     "includeSeepage": true')
    print("   }")

def main():
    # Load data
    excel_data = load_excel_data()
    kc_data = load_kc_data()
    
    # Run validations
    validate_eto_calculations(excel_data)
    validate_kc_calculations(excel_data, kc_data)
    calculate_water_requirements(excel_data, kc_data)
    compare_with_ros_api()
    
    # Save validation summary
    validation_summary = {
        'validation_date': datetime.now().isoformat(),
        'eto_annual_average': excel_data['eto_data']['annual_average'],
        'rice_kc_average': excel_data['kc_summary']['ข้าว กข.(นาดำ)']['average_kc'],
        'seepage_rate': excel_data['parameters']['seepage_rate_mm_per_week'],
        'rice_area': excel_data['parameters']['planting_areas'][0]['area_rai'],
        'expected_values': {
            'may_daily_eto': excel_data['eto_data']['monthly_eto']['May'] / 31,
            'rice_max_kc': excel_data['kc_summary']['ข้าว กข.(นาดำ)']['max_kc'],
            'rice_weekly_etc': (excel_data['eto_data']['monthly_eto']['May'] / 31) * 
                              excel_data['kc_summary']['ข้าว กข.(นาดำ)']['average_kc'] * 7
        }
    }
    
    with open('ros_validation_summary.json', 'w', encoding='utf-8') as f:
        json.dump(validation_summary, f, ensure_ascii=False, indent=2)
    
    print("\n\nValidation summary saved to ros_validation_summary.json")

if __name__ == "__main__":
    main()