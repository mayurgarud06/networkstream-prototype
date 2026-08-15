package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.domain.HotspotObservation;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.HotspotObservationRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;

@Service
public class HotspotObservationService {
    private final HotspotObservationRepository observations;
    private final GatewayRepository gateways;

    public HotspotObservationService(HotspotObservationRepository observations, GatewayRepository gateways) {
        this.observations = observations;
        this.gateways = gateways;
    }

    @Transactional
    public void report(String gatewayId, ApiModels.HotspotScanReport report) {
        if (report == null || report.gatewayId() == null || !gatewayId.equals(report.gatewayId())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Gateway ID mismatch");
        }
        gateways.findById(gatewayId).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Gateway not registered: " + gatewayId));

        Instant observedAt = report.observedAt() == null ? Instant.now() : report.observedAt();
        for (ApiModels.HotspotObservation item : report.hotspots()) {
            if (item.ssid() == null || item.ssid().isBlank()) continue;
            observations.save(new HotspotObservation(
                    gatewayId, item.ssid().trim(), item.bssid(), item.signalDbm(),
                    item.frequency(), item.security(), observedAt));
        }
    }

    @Transactional(readOnly = true)
    public List<ApiModels.HotspotObservation> recent(int seconds) {
        int safeSeconds = Math.max(10, Math.min(seconds, 3600));
        return observations.findByObservedAtAfterOrderBySignalDbmDesc(Instant.now().minusSeconds(safeSeconds))
                .stream()
                .map(o -> new ApiModels.HotspotObservation(
                        o.getGatewayId(), o.getSsid(), o.getBssid(), o.getSignalDbm(),
                        o.getFrequency(), o.getSecurity(), o.getObservedAt()))
                .toList();
    }
}
