package com.networkstream.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.networkstream.service.HotspotService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(HotspotController.class)
class HotspotControllerTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper objectMapper;
    @MockBean HotspotService service;

    @Test
    void frontendEnrollmentPayloadMatchesApiContract() throws Exception {
        when(service.enroll(any())).thenReturn(new ApiModels.Hotspot(
                "HS-TEST", "Phone B", "Test Provider", 20.7, 77.0,
                "ONLINE", "FREE", 20, 0, "WIN-LAPTOP-01"));

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "Phone B", "aa:bb:cc:dd:ee:ff", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "WIN-LAPTOP-01");

        mvc.perform(post("/api/hotspots/enroll")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("HS-TEST"))
                .andExpect(jsonPath("$.gatewayId").value("WIN-LAPTOP-01"))
                .andExpect(jsonPath("$.status").value("ONLINE"));
    }
}
