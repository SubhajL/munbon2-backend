#!/usr/bin/env python3
"""
Extract ETo and Kc values from Thai Excel file for ROS validation
"""

import pandas as pd
import json
from datetime import datetime

def extract_eto_data(file_path):
    """Extract ETo data from Excel file"""
    print("Extracting ETo data...")
    
    # Read ETo sheet
    eto_df = pd.read_excel(file_path, sheet_name='ETo', header=None)
    
    # Find Nakhon Ratchasima station
    # Based on the structure, station names are in column 1, starting from row 3
    eto_data = {}
    
    # Month names are in row 2, columns 3-14 (Jan-Dec)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Find Nakhon Ratchasima row
    for row in range(3, eto_df.shape[0]):
        station = str(eto_df.iloc[row, 1])
        if 'นครราชสีมา' in station:
            print(f"Found Nakhon Ratchasima at row {row}")
            
            # Extract monthly values
            monthly_values = {}
            for col, month in enumerate(months, start=3):
                value = eto_df.iloc[row, col]
                if pd.notna(value):
                    monthly_values[month] = float(value)
            
            eto_data = {
                'station': 'นครราชสีมา',
                'monthly_eto': monthly_values,
                'annual_average': sum(monthly_values.values()) / len(monthly_values)
            }
            break
    
    return eto_data

def extract_kc_data(file_path):
    """Extract Kc values for different crops"""
    print("\nExtracting Kc data...")
    
    # Read Kc sheet
    kc_df = pd.read_excel(file_path, sheet_name='Kc', header=None)
    
    # Crop names are in row 2
    crops = kc_df.iloc[2, 1:].dropna().tolist()
    
    kc_data = {}
    
    # Weekly values start from row 5 (week 1)
    for col_idx, crop in enumerate(crops, start=1):
        weekly_values = []
        
        # Extract 52 weeks of data
        for week in range(52):
            row = 5 + week  # Starting from row 5
            if row < kc_df.shape[0]:
                value = kc_df.iloc[row, col_idx]
                if pd.notna(value):
                    weekly_values.append(float(value))
                else:
                    weekly_values.append(0.0)
        
        kc_data[crop] = {
            'weekly_values': weekly_values,
            'average': sum(weekly_values) / len([v for v in weekly_values if v > 0]) if any(v > 0 for v in weekly_values) else 0
        }
    
    return kc_data

def extract_fill_data(file_path):
    """Extract key parameters from fill_data sheet"""
    print("\nExtracting fill_data parameters...")
    
    # Read fill_data sheet
    fill_df = pd.read_excel(file_path, sheet_name='fill_data', header=None)
    
    parameters = {}
    
    # Based on exploration, key values are:
    # Row 3-4: Province info
    # Row 5: Seepage rate
    # Row 11: Planting areas
    
    # Province
    if pd.notna(fill_df.iloc[4, 2]):
        parameters['province'] = str(fill_df.iloc[4, 2])
    
    # Seepage rate (mm/week)
    if pd.notna(fill_df.iloc[5, 3]):
        parameters['seepage_rate_mm_per_week'] = float(fill_df.iloc[5, 3])
    
    # Rice planting areas
    rice_areas = []
    if pd.notna(fill_df.iloc[11, 3]):
        rice_areas.append({
            'type': 'นาปี',
            'area_rai': float(fill_df.iloc[11, 3])
        })
    
    # Look for more crop areas
    for row in range(10, min(50, fill_df.shape[0])):
        if 'พื้นที่ปลูกทั้งหมด' in str(fill_df.iloc[row, 0]):
            for col in range(1, min(10, fill_df.shape[1])):
                val = fill_df.iloc[row, col]
                if pd.notna(val) and isinstance(val, (int, float)) and val > 1000:
                    # Try to get crop type from nearby cells
                    crop_type = None
                    for check_row in range(max(0, row-5), row):
                        if 'ชนิดพืช' in str(fill_df.iloc[check_row, 0]):
                            crop_type = str(fill_df.iloc[check_row, col])
                            break
                    
                    if crop_type and pd.notna(crop_type):
                        rice_areas.append({
                            'type': crop_type,
                            'area_rai': float(val),
                            'location': f'row_{row}_col_{col}'
                        })
    
    parameters['planting_areas'] = rice_areas
    
    return parameters

def main():
    file_path = '/Users/subhajlimanond/dev/munbon2-backend/คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm'
    
    try:
        # Extract all data
        eto_data = extract_eto_data(file_path)
        kc_data = extract_kc_data(file_path)
        fill_data = extract_fill_data(file_path)
        
        # Create summary for validation
        validation_data = {
            'extraction_date': datetime.now().isoformat(),
            'source_file': file_path,
            'eto_data': eto_data,
            'kc_summary': {
                crop: {
                    'average_kc': data['average'],
                    'max_kc': max(data['weekly_values']),
                    'min_kc': min(data['weekly_values']),
                    'weeks_with_data': len([v for v in data['weekly_values'] if v > 0])
                }
                for crop, data in kc_data.items()
            },
            'parameters': fill_data
        }
        
        # Save to JSON
        output_file = 'excel_extracted_data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nData extracted and saved to {output_file}")
        
        # Print summary
        print("\n=== Extraction Summary ===")
        print(f"ETo Station: {eto_data.get('station', 'Not found')}")
        print(f"Annual Average ETo: {eto_data.get('annual_average', 0):.2f} mm")
        print(f"\nNumber of crops with Kc data: {len(kc_data)}")
        print(f"Province: {fill_data.get('province', 'Not found')}")
        print(f"Seepage rate: {fill_data.get('seepage_rate_mm_per_week', 0)} mm/week")
        print(f"Number of planting areas found: {len(fill_data.get('planting_areas', []))}")
        
        # Save detailed Kc data separately
        kc_output_file = 'kc_detailed_data.json'
        with open(kc_output_file, 'w', encoding='utf-8') as f:
            json.dump(kc_data, f, ensure_ascii=False, indent=2)
        print(f"\nDetailed Kc data saved to {kc_output_file}")
        
    except Exception as e:
        print(f"Error extracting data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()