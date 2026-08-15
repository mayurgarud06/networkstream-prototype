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

import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

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
        AtomicReference<Hotspot> saved = new AtomicReference<>();
        when(gateways.findById("GW-1")).thenReturn(Optional.of(gateway));
        when(hotspots.findByGatewayIdAndName("GW-1", "MyPhone")).thenReturn(Optional.empty());
        when(hotspots.save(any(Hotspot.class))).thenAnswer(invocation -> {
            Hotspot hotspot = invocation.getArgument(0);
            saved.set(hotspot);
            return hotspot;
        });

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "AA-BB-CC-DD-EE-FF", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "GW-1");

        var result = service.enroll(request);

        assertNotNull(saved.get());
        assertEquals("MyPhone", result.name());
        assertEquals("Test Provider", result.providerName());
        assertEquals("GW-1", result.gatewayId());
        assertEquals("ONLINE", result.status());
        assertEquals("aa:bb:cc:dd:ee:ff", saved.get().getBssid());
    }

    @Test
    void enrollReturnsExistingHotspotInsteadOfCreatingDuplicate() {
        Gateway gateway = new Gateway("GW-1");
        Hotspot existing = new Hotspot(
                "HS-EXISTING", "MyPhone", "Test Provider", 20.7, 77.0,
                "ACTIVE", "FREE", 20, 0, "GW-1", "aa:bb:cc:dd:ee:ff");
        when(gateways.findById("GW-1")).thenReturn(Optional.of(gateway));
        when(hotspots.findByGatewayIdAndName("GW-1", "MyPhone")).thenReturn(Optional.of(existing));

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "AA:BB:CC:DD:EE:FF", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "GW-1");

        var result = service.enroll(request);

        assertEquals("HS-EXISTING", result.id());
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

    @Test
    void enrollRejectsInvalidBssid() {
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));

        HotspotEnrollmentRequest request = new HotspotEnrollmentRequest(
                "MyPhone", "not-a-mac", "Test Provider",
                20.7, 77.0, "FREE", 20, 0, "GW-1");

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.enroll(request));

        assertEquals(400, ex.getStatusCode().value());
    }
}
