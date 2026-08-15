package com.networkstream.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.networkstream.service.HotspotService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
class HotspotControllerTest {
 private MockMvc mvc; private final ObjectMapper objectMapper=new ObjectMapper(); @Mock HotspotService service;
 @BeforeEach void setUp(){MockitoAnnotations.openMocks(this);mvc=MockMvcBuilders.standaloneSetup(new HotspotController(service)).build();}
 @Test void frontendEnrollmentPayloadMatchesApiContract() throws Exception {
  when(service.enroll(any())).thenReturn(new ApiModels.Hotspot("HS-TEST","Phone B","Test Provider",20.7,77.0,"ONLINE","FREE",20,0,"WIN-LAPTOP-01"));
  HotspotEnrollmentRequest request=new HotspotEnrollmentRequest("Phone B","aa:bb:cc:dd:ee:ff","Test Provider",20.7,77.0,"FREE",20,0,"WIN-LAPTOP-01");
  mvc.perform(post("/api/hotspots/enroll").contentType(MediaType.APPLICATION_JSON).content(objectMapper.writeValueAsString(request))).andExpect(status().isOk()).andExpect(jsonPath("$.id").value("HS-TEST")).andExpect(jsonPath("$.gatewayId").value("WIN-LAPTOP-01")).andExpect(jsonPath("$.status").value("ONLINE"));
 }
}
