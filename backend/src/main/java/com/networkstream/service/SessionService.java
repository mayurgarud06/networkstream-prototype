package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.domain.NetworkSession;
import com.networkstream.domain.Hotspot;
import com.networkstream.repository.NetworkSessionRepository;
import com.networkstream.repository.HotspotRepository;
import com.networkstream.repository.UsageEventRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@Service
public class SessionService {

    private final NetworkSessionRepository sessions;
    private final HotspotRepository hotspots;
    private final UsageEventRepository usageEvents;
    private final GatewayService gateways;

    public SessionService(
            NetworkSessionRepository sessions,
            HotspotRepository hotspots,
            UsageEventRepository usageEvents,
            GatewayService gateways
    ) {
        this.sessions = sessions;
        this.hotspots = hotspots;
        this.usageEvents = usageEvents;
        this.gateways = gateways;
    }

    @Transactional
    public ApiModels.Session connect(ApiModels.ConnectRequest request) {

        Hotspot hotspot = hotspots.findById(request.hotspotId())
                .orElseThrow(() -> notFound("Hotspot not found: " + request.hotspotId()));

        if (hotspot.getGatewayId() == null) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "Hotspot has no gateway"
            );
        }

        String gatewayId = hotspot.getGatewayId();

        int speed = Math.min(5, hotspot.getSpeedMbps());

        NetworkSession session = new NetworkSession(
                "SES-" + UUID.randomUUID(),
                request.userId(),
                hotspot.getId(),
                gatewayId,
                "FREE",
                speed,
                500
        );

        NetworkSession saved = sessions.save(session);

        gateways.bumpPolicy(gatewayId);

        return toModel(saved);
    }

    @Transactional
    public ApiModels.Session usage(
            String id,
            ApiModels.UsageRequest request
    ) {
        NetworkSession session = getEntity(id);

        long bytes = Math.max(0, request.bytesUsed());

        session.addUsageBytes(bytes);
        NetworkSession saved = sessions.save(session);

        usageEvents.save(
                new com.networkstream.domain.UsageEvent(
                        id,
                        0,
                        0,
                        bytes,
                        "SIMULATOR"
                )
        );

        return toModel(saved);
    }

    @Transactional
    public ApiModels.Session upgrade(String id) {

        NetworkSession session = getEntity(id);

        session.upgrade();

        NetworkSession saved = sessions.save(session);

        gateways.bumpPolicy(session.getGatewayId());

        return toModel(saved);
    }

    @Transactional
    public ApiModels.Session end(String id) {

        NetworkSession session = getEntity(id);

        session.end();

        NetworkSession saved = sessions.save(session);

        gateways.bumpPolicy(session.getGatewayId());

        return toModel(saved);
    }

    @Transactional(readOnly = true)
    public ApiModels.Session get(String id) {
        return toModel(getEntity(id));
    }

    private NetworkSession getEntity(String id) {
        return sessions.findById(id)
                .orElseThrow(() -> notFound("Session not found: " + id));
    }

    private ApiModels.Session toModel(NetworkSession s) {
        return new ApiModels.Session(
                s.getId(),
                s.getUserId(),
                s.getHotspotId(),
                s.getGatewayId(),
                s.getPlan(),
                s.getStatus(),
                s.getSpeedMbps(),
                s.getQuotaMb(),
                s.getUsedMb(),
                s.getCreatedAt()
        );
    }

    private ResponseStatusException notFound(String message) {
        return new ResponseStatusException(
                HttpStatus.NOT_FOUND,
                message
        );
    }
}
