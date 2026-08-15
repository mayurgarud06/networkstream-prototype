package com.networkstream.service;

import com.networkstream.api.ApiModels;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/**
 * Accepts Wi-Fi observations reported by a NetworkStream gateway.
 *
 * The gateway scan contract is intentionally kept separate from the managed
 * hotspot registry: discovering an SSID does not authorize NetworkStream to
 * use or advertise that network as a provider hotspot.
 */
@Service
public class HotspotObservationService {

    private final ConcurrentMap<String, List<ApiModels.HotspotObservation>> observations =
            new ConcurrentHashMap<>();

    /**
     * Records the latest scan for a gateway.
     *
     * GatewayController supplies the path gateway id separately, so the
     * gateway id in the report is validated before the observation is stored.
     */
    public void report(String gatewayId, ApiModels.HotspotScanReport report) {
        if (gatewayId == null || gatewayId.isBlank()) {
            throw new IllegalArgumentException("gatewayId is required");
        }
        if (report == null) {
            throw new IllegalArgumentException("scanReport is required");
        }
        if (report.gatewayId() == null || !gatewayId.equals(report.gatewayId())) {
            throw new IllegalArgumentException("Gateway ID mismatch");
        }

        List<ApiModels.HotspotObservation> scan = report.hotspots() == null
                ? List.of()
                : report.hotspots().stream()
                    .filter(Objects::nonNull)
                    .map(observation -> normalize(gatewayId, report, observation))
                    .toList();

        observations.put(gatewayId, scan);
    }

    /**
     * Returns the latest observations reported by a gateway.
     * This is kept package/service-local for the first PR; the HTTP read API
     * can consume it in the next change without coupling the gateway ingest
     * endpoint to the frontend representation.
     */
    public List<ApiModels.HotspotObservation> latest(String gatewayId) {
        if (gatewayId == null || gatewayId.isBlank()) {
            throw new IllegalArgumentException("gatewayId is required");
        }
        return observations.getOrDefault(gatewayId, List.of());
    }

    private ApiModels.HotspotObservation normalize(
            String gatewayId,
            ApiModels.HotspotScanReport report,
            ApiModels.HotspotObservation observation
    ) {
        String observationGatewayId = observation.gatewayId() == null
                ? gatewayId
                : observation.gatewayId();

        if (!gatewayId.equals(observationGatewayId)) {
            throw new IllegalArgumentException("Observation gateway ID mismatch");
        }

        return new ApiModels.HotspotObservation(
                gatewayId,
                observation.ssid(),
                observation.bssid(),
                observation.signalDbm(),
                observation.frequency(),
                observation.security(),
                observation.observedAt() != null ? observation.observedAt() : report.observedAt()
        );
    }
}
