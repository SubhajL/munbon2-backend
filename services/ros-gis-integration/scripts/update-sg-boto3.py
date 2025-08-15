#!/usr/bin/env python3
"""
Update Security Group for ROS/GIS Integration Service
Adds port 3022 to the EC2 instance security group
"""

import boto3
import sys
from botocore.exceptions import ClientError

# Configuration
INSTANCE_ID = "i-04ff727ac3337a608"
PORT = 3022
DESCRIPTION = "ROS/GIS Integration Service"

# Colors for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
NC = '\033[0m'

def find_instance_and_region():
    """Find the instance and its region"""
    regions = ['ap-southeast-1', 'us-east-1', 'us-west-2', 'eu-west-1', 'ap-northeast-1', 
               'ap-south-1', 'ap-northeast-2', 'ap-southeast-2', 'ca-central-1', 'eu-central-1']
    
    for region in regions:
        print(f"Checking region {region}...", end=' ')
        try:
            ec2 = boto3.client('ec2', region_name=region)
            response = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
            
            if response['Reservations']:
                print(f"{GREEN}Found!{NC}")
                instance = response['Reservations'][0]['Instances'][0]
                security_groups = instance['SecurityGroups']
                return region, security_groups
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                print("Not found")
            else:
                print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")
    
    return None, None

def check_existing_rule(ec2_client, sg_id, port):
    """Check if the port is already open in the security group"""
    try:
        response = ec2_client.describe_security_groups(GroupIds=[sg_id])
        
        for rule in response['SecurityGroups'][0]['IpPermissions']:
            if rule.get('FromPort') == port and rule.get('ToPort') == port:
                return True
        return False
    except Exception as e:
        print(f"{RED}Error checking existing rules: {e}{NC}")
        return False

def add_security_group_rule(ec2_client, sg_id, port):
    """Add the security group rule for the specified port"""
    try:
        response = ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': port,
                    'ToPort': port,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': DESCRIPTION}]
                }
            ]
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
            print(f"{YELLOW}Rule already exists{NC}")
            return True
        else:
            print(f"{RED}Error adding rule: {e}{NC}")
            return False

def main():
    print(f"{GREEN}Security Group Update for ROS/GIS Integration Service{NC}")
    print(f"Instance ID: {INSTANCE_ID}")
    print(f"Port: {PORT}")
    print()
    
    # Find instance and region
    print("Step 1: Finding instance...")
    region, security_groups = find_instance_and_region()
    
    if not region:
        print(f"{RED}Instance not found in any checked region{NC}")
        print("\nManual update required:")
        print("1. Log into AWS Console")
        print("2. Find instance with IP 43.209.22.250")
        print(f"3. Add inbound rule for TCP port {PORT}")
        return 1
    
    print(f"\n{GREEN}✓ Found instance in region: {region}{NC}")
    
    # Get the first security group
    sg_id = security_groups[0]['GroupId']
    sg_name = security_groups[0]['GroupName']
    print(f"{GREEN}✓ Security Group: {sg_name} ({sg_id}){NC}")
    
    # Create EC2 client for the region
    ec2 = boto3.client('ec2', region_name=region)
    
    # Check if rule exists
    print(f"\nStep 2: Checking if port {PORT} is already open...")
    if check_existing_rule(ec2, sg_id, PORT):
        print(f"{YELLOW}Port {PORT} is already open in the security group{NC}")
        print("\nService should be accessible at:")
        print(f"  http://43.209.22.250:{PORT}/health")
        print(f"  http://43.209.22.250:{PORT}/graphql")
        return 0
    
    # Add the rule
    print(f"\nStep 3: Adding security group rule for port {PORT}...")
    if add_security_group_rule(ec2, sg_id, PORT):
        print(f"{GREEN}✓ Successfully added port {PORT} to security group!{NC}")
        print("\nThe ROS/GIS Integration Service is now accessible at:")
        print(f"  http://43.209.22.250:{PORT}/health")
        print(f"  http://43.209.22.250:{PORT}/graphql")
        return 0
    else:
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Cancelled by user{NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{NC}")
        sys.exit(1)