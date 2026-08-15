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
        var report = new ApiModels.HotspotScanReport("GW-1", Instant.now(), List.of());

        var ex = assertThrows(ResponseStatusException.class, () -> service.report("GW-1", report));

        assertEquals(404, ex.getStatusCode().value());
        verify(observations, never()).save(any());
    }

    @Test
    void reportRejectsGatewayIdMismatch() {
        var report = new ApiModels.HotspotScanReport("GW-OTHER", Instant.now(), List.of());

        var ex = assertThrows(ResponseStatusException.class, () -> service.report("GW-1", report));

        assertEquals(400, ex.getStatusCode().value());
        verifyNoInteractions(gateways);
        verify(observations, never()).save(any());
    }

    @Test
    void reportPersistsOnlyNonBlankObservedSsids() {
        Instant t = Instant.parse("2026-08-15T10:00:00Z");
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));
        when(observations.findFirstByGatewayIdAndBssid("GW-1", "aa:bb")).thenReturn(Optional.empty());
        var report = new ApiModels.HotspotScanReport("GW-1", t, List.of(
                new ApiModels.HotspotObservation("GW-1", " PhoneA ", "aa:bb", null, "2412 MHz", "WPA2", t),
                new ApiModels.HotspotObservation("GW-1", "   ", "cc:dd", -50, "2437 MHz", "WPA2", t)));

        service.report("GW-1", report);

        ArgumentCaptor<HotspotObservation> captor = ArgumentCaptor.forClass(HotspotObservation.class);
        verify(observations, times(1)).save(captor.capture());
        assertEquals("PhoneA", captor.getValue().getSsid());
        assertEquals("GW-1", captor.getValue().getGatewayId());
        assertEquals("aa:bb", captor.getValue().getBssid());
        assertEquals(t, captor.getValue().getObservedAt());
    }

    @Test
    void reportUpdatesExistingBssidInsteadOfCreatingDuplicate() {
        Instant oldTime = Instant.parse("2026-08-15T10:00:00Z");
        Instant newTime = Instant.parse("2026-08-15T10:00:30Z");
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));
        HotspotObservation existing = new HotspotObservation(
                "GW-1", "PhoneA", "aa:bb", 70, "2412 MHz", "WPA2", oldTime);
        when(observations.findFirstByGatewayIdAndBssid("GW-1", "aa:bb"))
                .thenReturn(Optional.of(existing));
        var report = new ApiModels.HotspotScanReport("GW-1", newTime, List.of(
                new ApiModels.HotspotObservation("GW-1", "PhoneA", "AA-BB", 90, "2412 MHz", "WPA2", newTime)));

        service.report("GW-1", report);

        verify(observations, times(1)).save(existing);
        assertEquals(90, existing.getSignalDbm());
        assertEquals("aa:bb", existing.getBssid());
        assertEquals(newTime, existing.getObservedAt());
        verify(observations, never()).save(argThat(value -> value != existing));
    }

    @Test
    void reportRejectsObservationBelongingToAnotherGateway() {
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));
        var report = new ApiModels.HotspotScanReport("GW-1", Instant.now(), List.of(
                new ApiModels.HotspotObservation("GW-2", "PhoneB", "aa:bb", null, "2412 MHz", "OPEN", null)));

        var ex = assertThrows(ResponseStatusException.class, () -> service.report("GW-1", report));

        assertEquals(400, ex.getStatusCode().value());
        verify(observations, never()).save(any());
    }

    @Test
    void recentReturnsOnlyOneEntryPerBssid() {
        Instant first = Instant.parse("2026-08-15T10:00:00Z");
        Instant second = Instant.parse("2026-08-15T10:00:30Z");
        HotspotObservation older = new HotspotObservation("GW-1", "PhoneA", "aa:bb", 70, "2412 MHz", "WPA2", first);
        HotspotObservation newer = new HotspotObservation("GW-2", "PhoneA", "aa:bb", 90, "2412 MHz", "WPA2", second);
        when(observations.findByObservedAtAfterOrderBySignalDbmDesc(any())).thenReturn(List.of(older, newer));

        var result = service.recent(180);

        assertEquals(1, result.size());
        assertEquals("GW-2", result.get(0).gatewayId());
        assertEquals(second, result.get(0).observedAt());
    }

    @Test
    void reportAcceptsNullHotspotListAsEmptyScan() {
        when(gateways.findById("GW-1")).thenReturn(Optional.of(new Gateway("GW-1")));
        var report = new ApiModels.HotspotScanReport("GW-1", Instant.now(), null);

        assertDoesNotThrow(() -> service.report("GW-1", report));
        verify(observations, never()).save(any());
    }
}
