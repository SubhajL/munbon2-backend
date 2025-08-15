#!/bin/bash

# Script to find which region your EC2 instance is in
INSTANCE_ID="i-04ff727ac3337a608"

echo "🔍 Searching for instance $INSTANCE_ID in all regions..."

# List of all AWS regions
REGIONS=$(aws ec2 describe-regions --query "Regions[].RegionName" --output text)

for region in $REGIONS; do
    echo -n "Checking $region... "
    
    # Try to describe the instance in this region
    result=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $region --query "Reservations[0].Instances[0].[State.Name,PublicIpAddress]" --output text 2>&1)
    
    if [[ ! "$result" =~ "InvalidInstanceID.NotFound" ]] && [[ ! "$result" =~ "error" ]]; then
        echo "✅ FOUND!"
        echo ""
        echo "Instance Details:"
        echo "Region: $region"
        echo "State: $(echo $result | awk '{print $1}')"
        echo "Public IP: $(echo $result | awk '{print $2}')"
        echo ""
        
        # Get security group details
        echo "Security Group Info:"
        aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $region \
            --query "Reservations[0].Instances[0].SecurityGroups[*].[GroupId,GroupName]" \
            --output table
        
        break
    else
        echo "❌"
    fi
done