package com.networkstream.api;

import com.networkstream.domain.Gateway;
import com.networkstream.service.GatewayService;
import com.networkstream.service.HotspotObservationService;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class GatewayControllerTest {

    @Test
    void scanReturnsTypedJsonResponse() {
        GatewayService gatewayService = mock(GatewayService.class);
        HotspotObservationService observationService = mock(HotspotObservationService.class);
        GatewayController controller = new GatewayController(gatewayService, observationService);

        ApiModels.HotspotScanReport report = new ApiModels.HotspotScanReport("GW-1", Instant.now(), List.of());
        ApiModels.GatewayScanResponse response = controller.scan("GW-1", report);

        assertEquals("OK", response.status());
        verify(observationService).report("GW-1", report);
    }

    @Test
    void listDelegatesToGatewayService() {
        GatewayService gatewayService = mock(GatewayService.class);
        HotspotObservationService observationService = mock(HotspotObservationService.class);
        GatewayController controller = new GatewayController(gatewayService, observationService);
        List<Gateway> gateways = List.of(new Gateway("GW-1"));
        when(gatewayService.list()).thenReturn(gateways);

        assertEquals(gateways, controller.list());
    }
}
