package com.networkstream.service;

import com.networkstream.api.HotspotEnrollmentRequest;
import com.networkstream.domain.Gateway;
import com.networkstream.domain.Hotspot;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.HotspotRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class HotspotServiceTest {

    @Mock HotspotRepository hotspots;
    @Mock GatewayRepository gateways;
    @InjectMocks HotspotService service;

    @Test
    void enrollRequiresRegisteredGateway() {
        when(gateways.findById("GW-1")).thenReturn(Optional.empty());

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "AA:BB:CC:DD:EE:FF", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "GW-1");

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.enroll(request));

        assertEquals(404, ex.getStatusCode().value());
    }

    @Test
    void enrollCreatesManagedHotspotForRegisteredGateway() {
        Gateway gateway = new Gateway("GW-1");
        when(gateways.findById("GW-1")).thenReturn(Optional.of(gateway));
        when(hotspots.save(any(Hotspot.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(hotspots.findAllByOrderByNameAsc()).thenAnswer(invocation ->
                List.of(new Hotspot("HS-TEST", "MyPhone", "Test Provider", 20.7, 77.0,
                        "ACTIVE", "FREE", 20, 0, "GW-1")));

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "AA:BB:CC:DD:EE:FF", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "GW-1");

        var result = service.enroll(request);

        assertEquals("MyPhone", result.name());
        assertEquals("Test Provider", result.providerName());
        assertEquals("GW-1", result.gatewayId());
        assertEquals("ACTIVE", result.status());
    }

    @Test
    void enrollRejectsInvalidSpeed() {
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "AA:BB:CC:DD:EE:FF", "Test Provider",
                20.7, 77.0, "FREE", 0, 0, "GW-1");

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.enroll(request));

        assertEquals(400, ex.getStatusCode().value());
    }
}
