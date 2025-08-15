#!/usr/bin/env python3
import pymssql
import pandas as pd
from datetime import datetime
import sys

# Database connection details
DB_CONFIG = {
    'server': 'moonup.hopto.org',
    'port': 1433,
    'user': 'sa',
    'password': 'bangkok1234',
    'database': 'db_scada'
}

def connect_to_database():
    """Establish connection to MSSQL database"""
    try:
        conn = pymssql.connect(**DB_CONFIG)
        print("Successfully connected to database")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def query_aos_data(conn, start_date, end_date):
    """Query AOS weather data for the specified date range"""
    query = """
    SELECT 
        id,
        data_datetime,
        battery,
        windspeed,
        windmax,
        raingauge,
        temp,
        winddirect,
        solar
    FROM tb_aos
    WHERE data_datetime >= %s AND data_datetime <= %s
    ORDER BY data_datetime
    """
    
    try:
        print(f"Querying data from {start_date} to {end_date}...")
        df = pd.read_sql(query, conn, params=(start_date, end_date))
        print(f"Retrieved {len(df)} records")
        return df
    except Exception as e:
        print(f"Error querying data: {e}")
        return None

def export_to_excel(df, filename):
    """Export dataframe to Excel with formatting"""
    try:
        # Create Excel writer with xlsxwriter engine
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write dataframe to Excel
            df.to_excel(writer, sheet_name='AOS Weather Data', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['AOS Weather Data']
            
            # Add header formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            # Write headers with formatting
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Set column widths
            worksheet.set_column('A:A', 10)  # id
            worksheet.set_column('B:B', 20)  # data_datetime
            worksheet.set_column('C:C', 12)  # battery
            worksheet.set_column('D:D', 12)  # windspeed
            worksheet.set_column('E:E', 12)  # windmax
            worksheet.set_column('F:F', 12)  # raingauge
            worksheet.set_column('G:G', 12)  # temp
            worksheet.set_column('H:H', 12)  # winddirect
            worksheet.set_column('I:I', 12)  # solar
            
            # Add number formatting
            num_format = workbook.add_format({'num_format': '0.00'})
            worksheet.set_column('C:I', 12, num_format)
            
            # Add date formatting
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
            worksheet.set_column('B:B', 20, date_format)
            
        print(f"Data exported successfully to {filename}")
        return True
    except Exception as e:
        print(f"Error exporting to Excel: {e}")
        return False

def main():
    # Date range
    start_date = '2024-07-04 00:00:00'
    end_date = '2024-10-31 23:59:59'
    
    # Output filename
    output_file = 'aos_weather_data_2024-07-04_to_2024-10-31.xlsx'
    
    # Connect to database
    conn = connect_to_database()
    
    try:
        # Query data
        df = query_aos_data(conn, start_date, end_date)
        
        if df is not None and not df.empty:
            # Add some basic statistics
            print("\nData Summary:")
            print(f"Date range: {df['data_datetime'].min()} to {df['data_datetime'].max()}")
            print(f"Temperature range: {df['temp'].min():.2f}°C to {df['temp'].max():.2f}°C")
            print(f"Total rainfall: {df['raingauge'].sum():.2f} mm")
            print(f"Average temperature: {df['temp'].mean():.2f}°C")
            
            # Export to Excel
            export_to_excel(df, output_file)
        else:
            print("No data retrieved")
            
    finally:
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    main()