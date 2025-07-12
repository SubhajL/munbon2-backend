# Build stage
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy pom.xml and download dependencies (cached layer)
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source code and build
COPY src ./src
RUN mvn clean package -DskipTests -Dspring-boot.repackage.excludeDevtools=true

# Extract layers for better caching
RUN java -Djarmode=layertools -jar target/*.jar extract

# Production stage - optimized for JVM and security
FROM eclipse-temurin:17-jre-alpine AS production

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init curl && \
    addgroup -g 1000 munbon && \
    adduser -u 1000 -G munbon -s /bin/sh -D munbon

WORKDIR /app

# Copy extracted layers in order of change frequency
COPY --from=builder --chown=munbon:munbon /app/dependencies/ ./
COPY --from=builder --chown=munbon:munbon /app/spring-boot-loader/ ./
COPY --from=builder --chown=munbon:munbon /app/snapshot-dependencies/ ./
COPY --from=builder --chown=munbon:munbon /app/application/ ./

USER munbon

EXPOSE 8080

# JVM optimizations for containers
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:InitialRAMPercentage=50.0 -XX:+UseG1GC"

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["dumb-init", "--"]
CMD ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.JarLauncher"]

# Development stage with hot-reload
FROM maven:3.9-eclipse-temurin-17 AS development

WORKDIR /app

# Install development tools
RUN apt-get update && \
    apt-get install -y inotify-tools && \
    rm -rf /var/lib/apt/lists/*

# Copy pom.xml
COPY pom.xml .

# Download dependencies
RUN mvn dependency:go-offline -B

EXPOSE 8080
EXPOSE 35729

# Development command with spring-boot-devtools
CMD ["mvn", "spring-boot:run", "-Dspring-boot.run.fork=false"]