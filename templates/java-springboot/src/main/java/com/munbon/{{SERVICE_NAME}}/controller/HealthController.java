package com.munbon.{{SERVICE_NAME}}.controller;

import com.munbon.{{SERVICE_NAME}}.dto.HealthResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/health")
@Tag(name = "Health", description = "Health check endpoints")
public class HealthController {
    
    @Value("${spring.application.name}")
    private String serviceName;
    
    @Value("${app.version:1.0.0}")
    private String version;
    
    @GetMapping
    @Operation(summary = "Health check", description = "Returns the health status of the service")
    public ResponseEntity<HealthResponse> health() {
        Map<String, String> checks = new HashMap<>();
        checks.put("database", "ok");
        checks.put("cache", "ok");
        
        HealthResponse response = HealthResponse.builder()
            .status("healthy")
            .service(serviceName)
            .version(version)
            .timestamp(Instant.now())
            .checks(checks)
            .build();
        
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/ready")
    @Operation(summary = "Readiness check", description = "Returns the readiness status of the service")
    public ResponseEntity<HealthResponse> ready() {
        HealthResponse response = HealthResponse.builder()
            .status("ready")
            .service(serviceName)
            .version(version)
            .timestamp(Instant.now())
            .build();
        
        return ResponseEntity.ok(response);
    }
}