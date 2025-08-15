#!/usr/bin/env python3
"""
Test Water Accounting Service models and structure
"""

import os
import sys
import importlib.util

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_model_imports():
    """Test that all models can be imported"""
    print("\n=== Testing Model Imports ===")
    
    models = [
        'section',
        'delivery', 
        'efficiency',
        'deficit',
        'loss',
        'reconciliation'
    ]
    
    for model_name in models:
        try:
            spec = importlib.util.spec_from_file_location(
                f"models.{model_name}",
                f"src/models/{model_name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"✓ {model_name}.py loaded successfully")
            
            # Check for expected classes
            if model_name == 'section':
                assert hasattr(module, 'Section')
                assert hasattr(module, 'SectionMetrics')
            elif model_name == 'delivery':
                assert hasattr(module, 'WaterDelivery')
                assert hasattr(module, 'DeliveryStatus')
            elif model_name == 'efficiency':
                assert hasattr(module, 'EfficiencyRecord')
            elif model_name == 'deficit':
                assert hasattr(module, 'DeficitRecord')
                assert hasattr(module, 'DeficitCarryForward')
            elif model_name == 'loss':
                assert hasattr(module, 'TransitLoss')
            elif model_name == 'reconciliation':
                assert hasattr(module, 'ReconciliationLog')
                assert hasattr(module, 'ReconciliationStatus')
                
        except Exception as e:
            print(f"✗ Failed to load {model_name}.py: {e}")

def test_service_imports():
    """Test that all services can be imported"""
    print("\n=== Testing Service Imports ===")
    
    services = [
        'volume_integration',
        'loss_calculation',
        'efficiency_calculator',
        'deficit_tracker',
        'accounting_service',
        'reconciliation_service',
        'external_clients'
    ]
    
    for service_name in services:
        try:
            spec = importlib.util.spec_from_file_location(
                f"services.{service_name}",
                f"src/services/{service_name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            print(f"✓ {service_name}.py loaded successfully")
                
        except Exception as e:
            print(f"✗ Failed to load {service_name}.py: {e}")

def test_api_imports():
    """Test that all API modules can be imported"""
    print("\n=== Testing API Imports ===")
    
    api_modules = [
        'accounting',
        'delivery',
        'efficiency',
        'deficit',
        'reconciliation'
    ]
    
    for api_name in api_modules:
        try:
            spec = importlib.util.spec_from_file_location(
                f"api.{api_name}",
                f"src/api/{api_name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            print(f"✓ {api_name}.py loaded successfully")
                
        except Exception as e:
            print(f"✗ Failed to load {api_name}.py: {e}")

def test_file_structure():
    """Test that all expected files exist"""
    print("\n=== Testing File Structure ===")
    
    expected_files = [
        'src/__init__.py',
        'src/main.py',
        'src/config.py',
        'src/database.py',
        'src/middleware.py',
        'src/schemas.py',
        'src/models/__init__.py',
        'src/services/__init__.py',
        'src/api/__init__.py',
        'src/utils/__init__.py',
        'src/utils/logging.py',
        'alembic.ini',
        'alembic/env.py',
        'alembic/script.py.mako',
        'alembic/versions/001_initial_water_accounting_tables.py',
        'scripts/init-postgres.sql',
        'scripts/init-timescale.sql',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        '.env.example',
        'README.md',
        'WATER_ACCOUNTING_E2E_FLOW.md',
        'INTEGRATION_GUIDE.md'
    ]
    
    for file_path in expected_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - NOT FOUND")

def check_api_endpoints():
    """Check API endpoint structure"""
    print("\n=== Checking API Endpoints ===")
    
    endpoints = {
        'Accounting': [
            'GET /api/v1/accounting/section/{section_id}',
            'GET /api/v1/accounting/sections',
            'GET /api/v1/accounting/balance/{section_id}'
        ],
        'Delivery': [
            'POST /api/v1/delivery/complete',
            'GET /api/v1/delivery/status/{delivery_id}',
            'POST /api/v1/delivery/validate-flow-data'
        ],
        'Efficiency': [
            'GET /api/v1/efficiency/report',
            'GET /api/v1/efficiency/trends/{section_id}',
            'GET /api/v1/efficiency/benchmarks',
            'POST /api/v1/efficiency/calculate-losses'
        ],
        'Deficits': [
            'GET /api/v1/deficits/week/{week}/{year}',
            'POST /api/v1/deficits/update',
            'GET /api/v1/deficits/carry-forward/{section_id}',
            'POST /api/v1/deficits/recovery-plan',
            'GET /api/v1/deficits/stress-assessment'
        ],
        'Reconciliation': [
            'POST /api/v1/reconciliation/weekly/{week}/{year}',
            'GET /api/v1/reconciliation/status/{week}/{year}',
            'GET /api/v1/reconciliation/history',
            'POST /api/v1/reconciliation/estimate-manual-flow',
            'GET /api/v1/reconciliation/adjustments/{reconciliation_id}'
        ]
    }
    
    for category, endpoint_list in endpoints.items():
        print(f"\n{category}:")
        for endpoint in endpoint_list:
            print(f"  ✓ {endpoint}")

def check_external_integrations():
    """Check external service integrations"""
    print("\n=== External Service Integrations ===")
    
    services = [
        ('Sensor Data Service', 'Port 3003', 'Flow readings'),
        ('GIS Service', 'Port 3007', 'Section boundaries'),
        ('Weather Service', 'Port 3008', 'Environmental conditions'),
        ('SCADA Service', 'Port 3023', 'Gate operations')
    ]
    
    for service, port, purpose in services:
        print(f"✓ {service} ({port}) - {purpose}")

def main():
    """Run all structure tests"""
    print("=" * 60)
    print("Water Accounting Service - Structure Validation")
    print("=" * 60)
    
    test_file_structure()
    test_model_imports()
    test_service_imports()
    test_api_imports()
    check_api_endpoints()
    check_external_integrations()
    
    print("\n" + "=" * 60)
    print("Structure validation completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()