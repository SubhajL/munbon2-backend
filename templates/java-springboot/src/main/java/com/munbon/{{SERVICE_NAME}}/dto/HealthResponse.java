package com.munbon.{{SERVICE_NAME}}.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HealthResponse {
    private String status;
    private String service;
    private String version;
    private Instant timestamp;
    private Map<String, String> checks;
}