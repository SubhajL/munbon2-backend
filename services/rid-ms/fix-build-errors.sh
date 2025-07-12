#!/bin/bash

echo "Installing missing dependencies for RID-MS service..."

# Install type definitions
npm install --save-dev \
  @types/node \
  @types/aws-lambda \
  @types/express \
  @types/multer \
  @types/pino \
  @types/uuid \
  @types/fs-extra \
  @types/pg \
  @types/adm-zip \
  @types/proj4 \
  @types/geojson \
  @types/cors \
  @types/bull

# Install missing runtime dependencies
npm install \
  aws-lambda \
  express \
  multer \
  pino \
  uuid \
  fs-extra \
  pg \
  express-validator \
  geojson \
  cors \
  bull \
  kafkajs \
  dbffile \
  shapefile \
  proj4 \
  @turf/turf

echo "Dependencies installed. Now building..."
npm run build