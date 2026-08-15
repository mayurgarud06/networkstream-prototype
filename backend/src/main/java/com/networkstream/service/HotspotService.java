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
        if (request == null || request.ssid() == null || request.ssid().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ssid is required");
        }
        if (request.gatewayId() == null || request.gatewayId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "gatewayId is required");
        }
        gateways.findById(request.gatewayId()).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "Gateway not registered: " + request.gatewayId()));
        if (request.speedMbps() <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "speedMbps must be positive");
        }
        if (request.priceInr() < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "priceInr cannot be negative");
        }

        String id = "HS-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        Hotspot hotspot = new Hotspot(
                id,
                request.ssid().trim(),
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
                request.gatewayId()
        );

        hotspots.save(hotspot);
        return list().stream()
                .filter(h -> id.equals(h.id()))
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "Hotspot enrollment failed"));
    }
}
