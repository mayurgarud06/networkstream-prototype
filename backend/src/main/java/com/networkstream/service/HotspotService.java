package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.api.HotspotEnrollmentRequest;
import com.networkstream.domain.Hotspot;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.HotspotRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class HotspotService {

    private final HotspotRepository hotspots;
    private final GatewayRepository gateways;

    public HotspotService(
            HotspotRepository hotspots,
            GatewayRepository gateways
    ) {
        this.hotspots = hotspots;
        this.gateways = gateways;
    }

    public List<ApiModels.Hotspot> list() {

        Instant onlineSince = Instant.now().minusSeconds(30);

        return hotspots.findAllByOrderByNameAsc()
                .stream()
                .map(h -> {

                    String status = "OFFLINE";

                    if (h.getGatewayId() == null) {
                        status = h.getStatus();
                    } else {
                        var gateway = gateways.findById(h.getGatewayId());

                        if (gateway.isPresent()
                                && "ONLINE".equals(gateway.get().getStatus())
                                && gateway.get().getLastHeartbeat() != null
                                && gateway.get().getLastHeartbeat().isAfter(onlineSince)) {
                            status = "ONLINE";
                        }
                    }

                    return new ApiModels.Hotspot(
                            h.getId(),
                            h.getName(),
                            h.getProviderName(),
                            h.getLatitude(),
                            h.getLongitude(),
                            status,
                            h.getAccessType(),
                            h.getSpeedMbps(),
                            h.getPriceInr(),
                            h.getGatewayId()
                    );
                })
                .toList();
    }

    @Transactional
    public ApiModels.Hotspot enroll(HotspotEnrollmentRequest request) {
        validateEnrollment(request);

        gateways.findById(request.gatewayId()).orElseThrow(() ->
                new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Gateway not registered: " + request.gatewayId()));

        String ssid = request.ssid().trim();
        String bssid = normalizeBssid(request.bssid());

        // Do not create duplicate managed entries when the provider submits
        // the same observed network more than once.
        Hotspot existing = hotspots.findByGatewayIdAndName(request.gatewayId(), ssid)
                .orElse(null);
        if (existing != null) {
            return toApiHotspot(existing);
        }

        String id = "HS-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        Hotspot hotspot = new Hotspot(
                id,
                ssid,
                request.providerName() == null || request.providerName().isBlank()
                        ? "Provider"
                        : request.providerName().trim(),
                request.latitude(),
                request.longitude(),
                "ACTIVE",
                request.accessType() == null || request.accessType().isBlank()
                        ? "FREE"
                        : request.accessType().trim().toUpperCase(),
                request.speedMbps(),
                request.priceInr(),
                request.gatewayId(),
                bssid
        );

        return toApiHotspot(hotspots.save(hotspot));
    }

    private void validateEnrollment(HotspotEnrollmentRequest request) {
        if (request == null || request.ssid() == null || request.ssid().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ssid is required");
        }
        if (request.ssid().trim().length() > 160) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ssid is too long");
        }
        if (request.gatewayId() == null || request.gatewayId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "gatewayId is required");
        }
        if (!Double.isFinite(request.latitude()) || request.latitude() < -90 || request.latitude() > 90) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "latitude must be between -90 and 90");
        }
        if (!Double.isFinite(request.longitude()) || request.longitude() < -180 || request.longitude() > 180) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "longitude must be between -180 and 180");
        }
        if (request.speedMbps() <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "speedMbps must be positive");
        }
        if (request.priceInr() < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "priceInr cannot be negative");
        }
        if (request.accessType() != null && !request.accessType().isBlank()) {
            String accessType = request.accessType().trim().toUpperCase();
            if (!"FREE".equals(accessType) && !"PREMIUM".equals(accessType)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "accessType must be FREE or PREMIUM");
            }
        }
        if (request.bssid() != null && !request.bssid().isBlank()
                && !request.bssid().trim().matches("(?i)^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "bssid must be a valid MAC address");
        }
    }

    private String normalizeBssid(String bssid) {
        if (bssid == null || bssid.isBlank()) {
            return null;
        }
        return bssid.trim().toLowerCase().replace('-', ':');
    }

    private ApiModels.Hotspot toApiHotspot(Hotspot h) {
        String status = "OFFLINE";
        if (h.getGatewayId() == null) {
            status = h.getStatus();
        } else {
            var gateway = gateways.findById(h.getGatewayId());
            if (gateway.isPresent()
                    && "ONLINE".equals(gateway.get().getStatus())
                    && gateway.get().getLastHeartbeat() != null
                    && gateway.get().getLastHeartbeat().isAfter(Instant.now().minusSeconds(30))) {
                status = "ONLINE";
            }
        }
        return new ApiModels.Hotspot(
                h.getId(), h.getName(), h.getProviderName(), h.getLatitude(), h.getLongitude(),
                status, h.getAccessType(), h.getSpeedMbps(), h.getPriceInr(), h.getGatewayId());
    }
}
