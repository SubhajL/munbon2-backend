#!/bin/bash

# Create Mosquitto password file
echo "Creating Mosquitto password file..."

# Create directory if it doesn't exist
mkdir -p ./mosquitto

# Generate password file using Docker
# This will prompt for password
docker run -it --rm \
  -v $(pwd)/mosquitto:/mosquitto/config \
  eclipse-mosquitto \
  mosquitto_passwd -c /mosquitto/config/passwd weather_user

echo "Mosquitto password file created at ./mosquitto/passwd"
echo "You can add more users with:"
echo "docker run -it --rm -v $(pwd)/mosquitto:/mosquitto/config eclipse-mosquitto mosquitto_passwd -b /mosquitto/config/passwd <username> <password>"