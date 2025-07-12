package com.munbon.{{SERVICE_NAME}}.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class HealthControllerTest {
    
    @Autowired
    private MockMvc mockMvc;
    
    @Test
    void healthCheck_ShouldReturnHealthy() throws Exception {
        mockMvc.perform(get("/health"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("healthy")))
            .andExpect(jsonPath("$.service", notNullValue()))
            .andExpect(jsonPath("$.version", notNullValue()))
            .andExpect(jsonPath("$.timestamp", notNullValue()));
    }
    
    @Test
    void readinessCheck_ShouldReturnReady() throws Exception {
        mockMvc.perform(get("/health/ready"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("ready")))
            .andExpect(jsonPath("$.service", notNullValue()))
            .andExpect(jsonPath("$.version", notNullValue()))
            .andExpect(jsonPath("$.timestamp", notNullValue()));
    }
}