FROM timescale/timescaledb:latest-pg15

# Install PostGIS
RUN apk add --no-cache \
    postgis \
    postgis-dev \
    && rm -rf /var/cache/apk/*

# Copy initialization scripts
COPY ./init-scripts/* /docker-entrypoint-initdb.d/

# Ensure scripts are executable
RUN chmod +x /docker-entrypoint-initdb.d/*.sql || true