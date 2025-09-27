#!/usr/bin/env python3
"""
CLI tool for water delivery analysis and simulation
"""
import click
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.scenarios.single_section_scenario import SingleSectionScenarioBuilder
from src.integrations.gis_client import GISClient
from src.integrations.flow_client import FlowMonitoringClient
from src.integrations.ros_client import ROSClient


@click.group()
@click.option('--gis-url', envvar='GIS_SERVICE_URL', default='http://localhost:8007', help='GIS service URL')
@click.option('--flow-url', envvar='FLOW_SERVICE_URL', default='http://localhost:8005', help='Flow monitoring service URL')
@click.option('--ros-url', envvar='ROS_SERVICE_URL', default='http://localhost:8004', help='ROS service URL')
@click.pass_context
def cli(ctx, gis_url, flow_url, ros_url):
    """Water Delivery Analysis CLI Tool"""
    ctx.ensure_object(dict)
    ctx.obj['gis_url'] = gis_url
    ctx.obj['flow_url'] = flow_url
    ctx.obj['ros_url'] = ros_url


@cli.command()
@click.argument('section_id')
@click.pass_context
def section_info(ctx, section_id):
    """Get detailed information about a section"""
    async def get_info():
        gis = GISClient(base_url=ctx.obj['gis_url'])
        
        try:
            info = await gis.get_section_details(section_id)
            
            click.echo(f"\n=== Section {section_id} ===")
            
            # Format data for table
            data = []
            for key, value in info.items():
                if key != 'geometry':  # Skip geometry data
                    data.append([key.replace('_', ' ').title(), str(value)])
            
            click.echo(tabulate(data, headers=['Property', 'Value'], tablefmt='grid'))
            
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await gis.close()
    
    asyncio.run(get_info())


@cli.command()
@click.argument('section_id')
@click.option('--depth', default=5.0, help='Water depth in cm')
@click.option('--json-output', is_flag=True, help='Output as JSON')
@click.pass_context
def analyze_delivery(ctx, section_id, depth, json_output):
    """Analyze water delivery path and requirements"""
    async def analyze():
        gis = GISClient(base_url=ctx.obj['gis_url'])
        flow = FlowMonitoringClient(base_url=ctx.obj['flow_url'])
        
        try:
            builder = SingleSectionScenarioBuilder(gis, flow)
            scenario = await builder.create_single_section_scenario(
                section_id=section_id,
                water_depth_cm=depth
            )
            
            if json_output:
                click.echo(json.dumps(scenario, indent=2, default=str))
            else:
                # Display formatted output
                target = scenario["target_section"]
                canal_vols = scenario["canal_volumes"]
                
                click.echo(f"\n=== Water Delivery Analysis ===")
                click.echo(f"Section: {section_id}")
                click.echo(f"Required Depth: {depth} cm")
                
                # Water calculations
                click.echo(f"\n📊 Water Calculations:")
                water_data = [
                    ["Section Area", f"{target['area_hectares']:.2f} hectares"],
                    ["Section Water Volume", f"{target['water_volume_m3']:,.0f} m³"],
                    ["Canal Fill Volume", f"{canal_vols['total_volume_m3']:,.0f} m³"],
                    ["Total Water Needed", f"{scenario['total_water_required_m3']:,.0f} m³"]
                ]
                click.echo(tabulate(water_data, tablefmt='simple'))
                
                # Delivery path summary
                click.echo(f"\n🛤️  Delivery Path:")
                path_data = [
                    ["Total Segments", len(scenario["delivery_path"])],
                    ["Total Distance", f"{canal_vols['total_distance_km']:.2f} km"],
                    ["Travel Time", f"{canal_vols['travel_time_hours']:.1f} hours"],
                    ["Delivery Gate", target.get('delivery_gate', 'N/A')]
                ]
                click.echo(tabulate(path_data, tablefmt='simple'))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await gis.close()
            await flow.close()
    
    asyncio.run(analyze())


@cli.command()
@click.argument('section_id')
@click.option('--limit', default=10, help='Maximum path segments to show')
@click.pass_context
def show_path(ctx, section_id, limit):
    """Show detailed delivery path to section"""
    async def show():
        gis = GISClient(base_url=ctx.obj['gis_url'])
        flow = FlowMonitoringClient(base_url=ctx.obj['flow_url'])
        
        try:
            builder = SingleSectionScenarioBuilder(gis, flow)
            path = await builder._trace_delivery_path(section_id)
            
            click.echo(f"\n=== Delivery Path to {section_id} ===")
            click.echo(f"Total segments: {len(path)}")
            
            # Format path data
            headers = ['#', 'From', 'To', 'Type', 'Distance (km)', 'Canal ID']
            data = []
            
            total_distance = 0
            for i, segment in enumerate(path[:limit]):
                distance = segment.get('distance_km', 0)
                total_distance += distance
                
                data.append([
                    i + 1,
                    segment['from'],
                    segment['to'],
                    segment['type'],
                    f"{distance:.2f}",
                    segment.get('canal_id', '-')
                ])
            
            click.echo(tabulate(data, headers=headers, tablefmt='grid'))
            
            if len(path) > limit:
                click.echo(f"\n... and {len(path) - limit} more segments")
            
            click.echo(f"\nTotal distance: {total_distance:.2f} km")
            
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await gis.close()
            await flow.close()
    
    asyncio.run(show())


@cli.command()
@click.argument('section_id')
@click.option('--depths', default='1,3,5,10', help='Comma-separated depths in cm')
@click.pass_context
def compare_depths(ctx, section_id, depths):
    """Compare water requirements for different depths"""
    async def compare():
        gis = GISClient(base_url=ctx.obj['gis_url'])
        flow = FlowMonitoringClient(base_url=ctx.obj['flow_url'])
        
        try:
            builder = SingleSectionScenarioBuilder(gis, flow)
            depth_list = [float(d) for d in depths.split(',')]
            
            results = []
            canal_volume = None
            
            for depth in depth_list:
                try:
                    scenario = await builder.create_single_section_scenario(
                        section_id=section_id,
                        water_depth_cm=depth
                    )
                    
                    # Canal volume should be same for all
                    if canal_volume is None:
                        canal_volume = scenario["canal_volumes"]["total_volume_m3"]
                    
                    results.append({
                        'depth': depth,
                        'section_water': scenario["target_section"]["water_volume_m3"],
                        'total': scenario["total_water_required_m3"]
                    })
                except Exception as e:
                    click.echo(f"Error for {depth}cm: {e}", err=True)
            
            if results:
                click.echo(f"\n=== Water Requirements for {section_id} ===")
                click.echo(f"Canal fill volume (constant): {canal_volume:,.0f} m³\n")
                
                headers = ['Depth (cm)', 'Section Water (m³)', 'Total Water (m³)', '% Canal']
                data = []
                
                for r in results:
                    canal_percent = (canal_volume / r['total']) * 100 if r['total'] > 0 else 0
                    data.append([
                        r['depth'],
                        f"{r['section_water']:,.0f}",
                        f"{r['total']:,.0f}",
                        f"{canal_percent:.1f}%"
                    ])
                
                click.echo(tabulate(data, headers=headers, tablefmt='grid'))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await gis.close()
            await flow.close()
    
    asyncio.run(compare())


@cli.command()
@click.argument('zone_id', type=int)
@click.option('--crop', help='Filter by crop type')
@click.option('--limit', default=20, help='Maximum sections to show')
@click.pass_context
def list_sections(ctx, zone_id, crop, limit):
    """List sections in a zone"""
    async def list_secs():
        gis = GISClient(base_url=ctx.obj['gis_url'])
        
        try:
            sections = await gis.get_sections_in_zone(zone_id)
            
            click.echo(f"\n=== Sections in Zone {zone_id} ===")
            click.echo(f"Total sections: {len(sections)}")
            
            # Filter by crop if specified
            if crop:
                sections = [s for s in sections if s.get('crop_type', '').lower() == crop.lower()]
                click.echo(f"Filtered by crop '{crop}': {len(sections)} sections")
            
            # Format data
            headers = ['Section ID', 'Area (ha)', 'Area (rai)', 'Crop Type', 'Delivery Gate']
            data = []
            
            for section in sections[:limit]:
                data.append([
                    section.get('section_id', '-'),
                    f"{section.get('area_hectares', 0):.2f}" if 'area_hectares' in section else '-',
                    f"{section.get('area_rai', 0):.2f}" if 'area_rai' in section else '-',
                    section.get('crop_type', '-'),
                    section.get('delivery_gate', '-')
                ])
            
            click.echo(tabulate(data, headers=headers, tablefmt='grid'))
            
            if len(sections) > limit:
                click.echo(f"\n... and {len(sections) - limit} more sections")
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await gis.close()
    
    asyncio.run(list_secs())


@cli.command()
@click.argument('gate_id')
@click.pass_context
def gate_info(ctx, gate_id):
    """Get gate properties and specifications"""
    async def get_gate():
        flow = FlowMonitoringClient(base_url=ctx.obj['flow_url'])
        
        try:
            props = await flow.get_gate_properties(gate_id)
            
            click.echo(f"\n=== Gate {gate_id} Properties ===")
            
            data = []
            for key, value in props.items():
                if key not in ['gate_id']:
                    data.append([key.replace('_', ' ').title(), str(value)])
            
            click.echo(tabulate(data, headers=['Property', 'Value'], tablefmt='grid'))
            
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await flow.close()
    
    asyncio.run(get_gate())


@cli.command()
@click.pass_context
def test_connections(ctx):
    """Test connections to all services"""
    async def test():
        services = [
            ('GIS', ctx.obj['gis_url'], GISClient),
            ('Flow Monitoring', ctx.obj['flow_url'], FlowMonitoringClient),
            ('ROS', ctx.obj['ros_url'], ROSClient)
        ]
        
        click.echo("\n=== Testing Service Connections ===")
        
        results = []
        for name, url, client_class in services:
            client = client_class(base_url=url)
            try:
                # Try to make a simple request
                if name == 'GIS':
                    await client.get_sections_in_zone(1)
                elif name == 'Flow Monitoring':
                    await client.get_gate_properties("TEST")
                elif name == 'ROS':
                    await client.get_area_info("TEST")
                
                results.append([name, url, "✓ Connected"])
            except Exception as e:
                results.append([name, url, f"✗ {str(e)[:50]}..."])
            finally:
                await client.close()
        
        click.echo(tabulate(results, headers=['Service', 'URL', 'Status'], tablefmt='grid'))
    
    asyncio.run(test())


if __name__ == '__main__':
    cli()