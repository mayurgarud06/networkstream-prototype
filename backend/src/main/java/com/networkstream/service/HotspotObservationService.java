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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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
        if (gatewayId == null || gatewayId.isBlank()
                || report == null || report.gatewayId() == null
                || !gatewayId.equals(report.gatewayId())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Gateway ID mismatch");
        }
        gateways.findById(gatewayId).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Gateway not registered: " + gatewayId));

        Instant observedAt = report.observedAt() == null ? Instant.now() : report.observedAt();
        if (report.hotspots() == null) {
            return;
        }

        for (ApiModels.HotspotObservation item : report.hotspots()) {
            if (item == null || item.ssid() == null || item.ssid().isBlank()) continue;
            if (item.gatewayId() != null && !gatewayId.equals(item.gatewayId())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Observation gateway ID mismatch");
            }

            String ssid = item.ssid().trim();
            String bssid = normalizeBssid(item.bssid());
            Instant itemObservedAt = item.observedAt() == null ? observedAt : item.observedAt();

            HotspotObservation existing = bssid == null
                    ? observations.findFirstByGatewayIdAndSsidAndBssidIsNull(gatewayId, ssid).orElse(null)
                    : observations.findFirstByGatewayIdAndBssid(gatewayId, bssid).orElse(null);

            if (existing == null) {
                observations.save(new HotspotObservation(
                        gatewayId, ssid, bssid, item.signalDbm(),
                        item.frequency(), item.security(), itemObservedAt));
            } else {
                existing.updateObservation(
                        ssid, bssid, item.signalDbm(), item.frequency(), item.security(), itemObservedAt);
                observations.save(existing);
            }
        }
    }

    @Transactional(readOnly = true)
    public List<ApiModels.HotspotObservation> recent(int seconds) {
        int safeSeconds = Math.max(10, Math.min(seconds, 3600));
        Map<String, HotspotObservation> unique = new LinkedHashMap<>();

        for (HotspotObservation observation : observations
                .findByObservedAtAfterOrderBySignalDbmDesc(Instant.now().minusSeconds(safeSeconds))) {
            String key = identityKey(observation);
            HotspotObservation current = unique.get(key);
            if (current == null || observation.getObservedAt().isAfter(current.getObservedAt())) {
                unique.put(key, observation);
            }
        }

        return unique.values().stream()
                .map(o -> new ApiModels.HotspotObservation(
                        o.getGatewayId(), o.getSsid(), o.getBssid(), o.getSignalDbm(),
                        o.getFrequency(), o.getSecurity(), o.getObservedAt()))
                .toList();
    }

    private String normalizeBssid(String bssid) {
        if (bssid == null || bssid.isBlank()) return null;
        return bssid.trim().toLowerCase().replace('-', ':');
    }

    private String identityKey(HotspotObservation observation) {
        if (observation.getBssid() != null && !observation.getBssid().isBlank()) {
            return "BSSID:" + observation.getBssid().trim().toLowerCase();
        }
        return "SSID:" + observation.getGatewayId() + ":" + observation.getSsid().trim().toLowerCase();
    }
}
