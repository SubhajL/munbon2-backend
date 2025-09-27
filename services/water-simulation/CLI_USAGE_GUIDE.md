# Water Delivery CLI Usage Guide

The CLI tool provides easy access to water delivery analysis without writing code.

## Installation

```bash
cd services/water-simulation
pip install -r requirements.txt
```

## Basic Usage

### 1. Get Section Information

```bash
# Get details for section 01-06-02-42
./cli/water_delivery_cli.py section-info 01-06-02-42

# Output:
=== Section 01-06-02-42 ===
┌─────────────────┬────────────────┐
│ Property        │ Value          │
├─────────────────┼────────────────┤
│ Section Id      │ 01-06-02-42    │
│ Zone            │ 6              │
│ Area Hectares   │ 125.50         │
│ Area Rai        │ 784.38         │
│ Crop Type       │ rice           │
│ Delivery Gate   │ GATE_06_42     │
└─────────────────┴────────────────┘
```

### 2. Analyze Water Delivery

```bash
# Analyze delivery for 5cm water depth
./cli/water_delivery_cli.py analyze-delivery 01-06-02-42 --depth 5

# Output:
=== Water Delivery Analysis ===
Section: 01-06-02-42
Required Depth: 5 cm

📊 Water Calculations:
Section Area             125.50 hectares
Section Water Volume     62,750 m³
Canal Fill Volume        85,230 m³
Total Water Needed       147,980 m³

🛤️  Delivery Path:
Total Segments    12
Total Distance    18.5 km
Travel Time       6.9 hours
Delivery Gate     GATE_06_42
```

### 3. Show Delivery Path

```bash
# Show detailed path to section
./cli/water_delivery_cli.py show-path 01-06-02-42 --limit 10

# Output shows each segment from source to destination
```

### 4. Compare Different Water Depths

```bash
# Compare water requirements for 1, 3, 5, and 10 cm
./cli/water_delivery_cli.py compare-depths 01-06-02-42 --depths 1,3,5,10

# Output:
=== Water Requirements for 01-06-02-42 ===
Canal fill volume (constant): 85,230 m³

┌────────────┬──────────────────┬─────────────────┬──────────┐
│ Depth (cm) │ Section Water    │ Total Water     │ % Canal  │
├────────────┼──────────────────┼─────────────────┼──────────┤
│ 1          │ 12,550 m³       │ 97,780 m³       │ 87.2%    │
│ 3          │ 37,650 m³       │ 122,880 m³      │ 69.4%    │
│ 5          │ 62,750 m³       │ 147,980 m³      │ 57.6%    │
│ 10         │ 125,500 m³      │ 210,730 m³      │ 40.4%    │
└────────────┴──────────────────┴─────────────────┴──────────┘
```

### 5. List Sections in Zone

```bash
# List sections in zone 6
./cli/water_delivery_cli.py list-sections 6 --limit 10

# Filter by crop type
./cli/water_delivery_cli.py list-sections 6 --crop rice
```

### 6. Get Gate Information

```bash
# Get properties for a specific gate
./cli/water_delivery_cli.py gate-info GATE_06_42

# Output:
=== Gate GATE_06_42 Properties ===
┌─────────────────┬────────────┐
│ Property        │ Value      │
├─────────────────┼────────────┤
│ Shape           │ rectangular│
│ Width M         │ 3.0        │
│ Height M        │ 2.0        │
│ Max Opening M   │ 2.0        │
│ K1              │ 0.85       │
│ K2              │ 0.92       │
└─────────────────┴────────────┘
```

### 7. Test Service Connections

```bash
# Verify all services are accessible
./cli/water_delivery_cli.py test-connections

# Output:
=== Testing Service Connections ===
┌───────────────────┬─────────────────────┬─────────────┐
│ Service           │ URL                 │ Status      │
├───────────────────┼─────────────────────┼─────────────┤
│ GIS              │ http://localhost:8007│ ✓ Connected │
│ Flow Monitoring  │ http://localhost:8005│ ✓ Connected │
│ ROS              │ http://localhost:8004│ ✓ Connected │
└───────────────────┴─────────────────────┴─────────────┘
```

## Advanced Options

### JSON Output

```bash
# Get results as JSON for processing
./cli/water_delivery_cli.py analyze-delivery 01-06-02-42 --json-output > analysis.json
```

### Custom Service URLs

```bash
# Use different service endpoints
./cli/water_delivery_cli.py --gis-url http://gis:8007 \
                            --flow-url http://flow:8005 \
                            section-info 01-06-02-42

# Or set environment variables
export GIS_SERVICE_URL=http://gis:8007
export FLOW_SERVICE_URL=http://flow:8005
./cli/water_delivery_cli.py section-info 01-06-02-42
```

## Scripting Examples

### Analyze Multiple Sections

```bash
#!/bin/bash
# analyze_multiple.sh

sections=("01-06-02-42" "01-06-02-43" "01-06-02-44")

for section in "${sections[@]}"; do
    echo "Analyzing $section..."
    ./cli/water_delivery_cli.py analyze-delivery "$section" --depth 5
    echo "---"
done
```

### Export All Sections in Zone

```bash
# Export all sections to CSV
./cli/water_delivery_cli.py list-sections 6 --limit 1000 | \
    grep -E "^\│" | grep -v "─" | \
    awk -F'│' '{print $2","$3","$4","$5","$6}' > zone_6_sections.csv
```

## Troubleshooting

### Connection Errors

```bash
# Check service status
./cli/water_delivery_cli.py test-connections

# Use verbose output for debugging
PYTHONPATH=. python -m cli.water_delivery_cli test-connections
```

### Section Not Found

```bash
# List available sections first
./cli/water_delivery_cli.py list-sections 6 --limit 50 | grep "01-06"
```

### Performance Tips

- Use `--limit` to reduce output for large zones
- Cache results with `--json-output` for repeated analysis
- Run multiple analyses in parallel for different sections