package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.domain.Hotspot;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.HotspotRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

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
}
