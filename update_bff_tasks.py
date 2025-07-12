#!/usr/bin/env python3
import json
import os

def update_tasks():
    # Read the current tasks.json
    with open('tasks/tasks.json', 'r') as f:
        data = json.load(f)
    
    # Update task 42
    for task in data['master']['tasks']:
        if task['id'] == 42:
            task['title'] = "Implement Setup BFF Service"
            task['description'] = "Develop a Backend-for-Frontend service for initial system setup and configuration, handling farmer registration, land parcel mapping, and initial water allocation setup."
            task['details'] = "Create Setup BFF using Node.js/TypeScript with Express.js or NestJS. Implement GraphQL endpoint optimized for setup workflows and multi-step processes. Create data aggregation layer to handle farmer registration data from multiple services (auth, user management, GIS). Implement wizard-style API flows for step-by-step configuration. Add validation for Thai National ID and land ownership documents. Integrate with GIS service for land parcel boundary definition and validation. Create APIs for initial water rights allocation based on land area and crop type. Implement bulk import capabilities for farmer data from CSV/Excel files. Add conflict resolution for overlapping land claims. Create approval workflow APIs for administrator verification. Implement data validation against government databases. Add progress tracking for multi-step setup processes."
            task['testStrategy'] = "Test GraphQL mutations for setup workflows. Verify data validation for Thai ID and land documents. Test GIS integration for parcel mapping. Validate bulk import with various file formats. Test conflict detection for overlapping parcels. Verify approval workflow state transitions. Test data aggregation from multiple services. Validate setup completion and system initialization. Test rollback capabilities for failed setups."
            break
    
    # Update task 43
    for task in data['master']['tasks']:
        if task['id'] == 43:
            task['title'] = "Implement Water Planning BFF Service"
            task['description'] = "Develop a specialized Backend-for-Frontend service for water planning activities, including irrigation scheduling, water allocation planning, and crop water requirement calculations."
            task['details'] = "Build Water Planning BFF using Node.js/TypeScript with Express.js or NestJS. Implement GraphQL APIs optimized for water planning workflows. Create data aggregation layer combining data from weather service, crop management, and water distribution services. Implement irrigation scheduling algorithms with support for multiple scheduling methods (ET-based, soil moisture-based, calendar-based). Create APIs for water budget calculations at field, zone, and system levels. Integrate with AquaCrop model for crop water requirement predictions. Implement optimization endpoints for water allocation across multiple fields. Add support for what-if scenarios and planning simulations. Create APIs for seasonal planning with historical data analysis. Implement conflict resolution for competing water demands. Add drought management planning endpoints. Create visualization APIs for water balance charts and allocation maps."
            task['testStrategy'] = "Test GraphQL queries for planning data aggregation. Verify irrigation scheduling algorithm accuracy. Test water budget calculations at multiple scales. Validate AquaCrop model integration. Test optimization algorithms with various constraints. Verify what-if scenario simulations. Test seasonal planning with historical data. Validate conflict resolution logic. Test drought scenario planning. Verify visualization data formatting."
            break
    
    # Add new task 55 - Water Control BFF
    new_task_55 = {
        "id": 55,
        "title": "Implement Water Control BFF Service",
        "description": "Develop a specialized Backend-for-Frontend service for real-time water control operations, including gate control, pump management, and emergency response interfaces.",
        "details": "Create Water Control BFF using Node.js/TypeScript with Express.js or NestJS. Implement WebSocket connections for real-time control updates and status monitoring. Create command APIs for gate operations (open/close/set position) with safety validations. Implement pump control endpoints with start/stop sequences and safety interlocks. Add real-time telemetry streaming for water levels, flow rates, and gate positions. Create emergency override APIs with proper authorization and audit logging. Implement control loop feedback APIs for automated control systems. Add support for manual override modes with operator tracking. Create batch control APIs for zone-wide operations. Implement predictive control interfaces for AI-based recommendations. Add alarm and alert aggregation from SCADA systems. Create mobile-optimized endpoints for field operator devices. Implement offline command queueing for unreliable network conditions.",
        "testStrategy": "Test WebSocket connections for real-time updates. Verify gate control commands with safety validations. Test pump control sequences and interlocks. Validate telemetry data streaming performance. Test emergency override authorization and logging. Verify control loop feedback accuracy. Test manual override tracking. Validate batch operations across multiple devices. Test offline command queueing and synchronization. Verify mobile endpoint optimization.",
        "priority": "high",
        "dependencies": [3, 4, 9, 10, 13, 20],
        "status": "pending",
        "subtasks": []
    }
    
    # Add new task 57 - Dashboard BFF
    new_task_57 = {
        "id": 57,
        "title": "Implement Dashboard BFF Service",
        "description": "Develop a specialized Backend-for-Frontend service for comprehensive dashboards, providing aggregated data views, KPIs, and analytics for different user roles including farmers, operators, and administrators.",
        "details": "Build Dashboard BFF using Node.js/TypeScript with Express.js or NestJS. Implement RESTful and GraphQL APIs optimized for dashboard data aggregation. Create role-specific dashboard endpoints (farmer dashboard, operator dashboard, admin dashboard). Implement real-time KPI calculations for water usage efficiency, system performance, and crop health metrics. Add time-series data aggregation for historical trending with configurable time windows. Create geospatial data aggregation for map-based visualizations. Implement caching strategies for frequently accessed metrics using Redis. Add support for custom dashboard configurations per user. Create alert summary endpoints with priority filtering. Implement comparative analytics APIs (year-over-year, zone comparisons). Add export capabilities for reports and data downloads. Create mobile-responsive data endpoints. Implement server-side data filtering and aggregation to minimize client processing.",
        "testStrategy": "Test data aggregation from multiple microservices. Verify role-based dashboard access. Test real-time KPI calculation accuracy. Validate time-series aggregation with various time windows. Test geospatial data formatting for maps. Verify caching performance and invalidation. Test custom dashboard persistence. Validate alert aggregation and filtering. Test comparative analytics calculations. Verify export functionality for various formats. Load test with concurrent dashboard users.",
        "priority": "high",
        "dependencies": [3, 4, 6, 8, 12, 13, 15, 17, 18, 22],
        "status": "pending",
        "subtasks": []
    }
    
    # Add new tasks to the list
    data['master']['tasks'].append(new_task_55)
    data['master']['tasks'].append(new_task_57)
    
    # Sort tasks by ID
    data['master']['tasks'].sort(key=lambda x: x['id'])
    
    # Write back to file
    with open('tasks/tasks.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("Tasks updated successfully!")
    print("- Task 42: Updated from 'Mobile BFF' to 'Setup BFF'")
    print("- Task 43: Updated from 'Web BFF' to 'Water Planning BFF'")
    print("- Task 55: Added 'Water Control BFF'")
    print("- Task 57: Added 'Dashboard BFF'")

if __name__ == "__main__":
    os.chdir('/Users/subhajlimanond/dev/munbon2-backend')
    update_tasks()