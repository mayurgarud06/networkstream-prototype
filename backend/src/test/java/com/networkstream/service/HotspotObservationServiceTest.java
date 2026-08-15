package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.domain.Gateway;
import com.networkstream.domain.HotspotObservation;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.HotspotObservationRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class HotspotObservationServiceTest {

    @Mock HotspotObservationRepository observations;
    @Mock GatewayRepository gateways;
    @InjectMocks HotspotObservationService service;

    @Test
    void reportRequiresRegisteredGateway() {
        when(gateways.findById("GW-1")).thenReturn(Optional.empty());
        ApiModels.HotspotScanReport report = new ApiModels.HotspotScanReport(
                "GW-1", Instant.now(), List.of());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.report("GW-1", report));

        assertEquals(404, ex.getStatusCode().value());
        verify(observations, never()).save(any());
    }

    @Test
    void reportRejectsGatewayIdMismatch() {
        ApiModels.HotspotScanReport report = new ApiModels.HotspotScanReport(
                "GW-OTHER", Instant.now(), List.of());

        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.report("GW-1", report));

        assertEquals(400, ex.getStatusCode().value());
        verifyNoInteractions(gateways);
        verify(observations, never()).save(any());
    }

    @Test
    void reportPersistsOnlyNonBlankObservedSsids() {
        Instant observedAt = Instant.parse("2026-08-15T10:00:00Z");
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));
        ApiModels.HotspotScanReport report = new ApiModels.HotspotScanReport(
                "GW-1", observedAt, List.of(
                        new ApiModels.HotspotObservation("GW-1", " PhoneA ", "aa:bb", null, "2412 MHz", "WPA2", observedAt),
                        new ApiModels.HotspotObservation("GW-1", "   ", "cc:dd", -50, "2437 MHz", "WPA2", observedAt)
                ));

        service.report("GW-1", report);

        ArgumentCaptor<HotspotObservation> captor = ArgumentCaptor.forClass(HotspotObservation.class);
        verify(observations, times(1)).save(captor.capture());
        assertEquals("PhoneA", captor.getValue().getSsid());
        assertEquals("GW-1", captor.getValue().getGatewayId());
        assertEquals(observedAt, captor.getValue().getObservedAt());
    }
}
