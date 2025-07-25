#!/usr/bin/env python3

import subprocess
import psutil
import socket

print("=== Checking Running Processes ===\n")

# Check Docker containers
print("1. Docker containers:")
try:
    result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("Docker not available or error accessing Docker")
except:
    print("Docker command not found")

# Check for specific processes
print("\n2. Application processes:")
found_processes = False
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
        if any(keyword in cmdline.lower() for keyword in ['munbon', 'sensor-data', 'flow-monitoring', 'gis-data']):
            print(f"PID {proc.info['pid']}: {proc.info['name']} - {cmdline[:100]}")
            found_processes = True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

if not found_processes:
    print("No munbon-related processes found")

# Check ports
print("\n3. Port usage:")
ports_to_check = {
    'PostgreSQL': range(5432, 5435),
    'Node services': range(3000, 3021),
    'Python services': range(8000, 8021)
}

for service, port_range in ports_to_check.items():
    print(f"\n{service}:")
    found_port = False
    for port in port_range:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            # Port is in use, try to find what's using it
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    try:
                        proc = psutil.Process(conn.pid)
                        print(f"  Port {port}: {proc.name()} (PID: {proc.pid})")
                        found_port = True
                    except:
                        print(f"  Port {port}: In use (unable to identify process)")
                        found_port = True
                    break
    
    if not found_port:
        print(f"  No services listening on {service} ports")