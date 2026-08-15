package com.networkstream.service;

import com.networkstream.api.ApiModels;
import com.networkstream.domain.Gateway;
import com.networkstream.repository.GatewayCommandRepository;
import com.networkstream.repository.GatewayRepository;
import com.networkstream.repository.NetworkSessionRepository;
import com.networkstream.repository.UsageEventRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import com.networkstream.domain.NetworkSession;

import java.util.List;

@Service
public class GatewayService {

    private final GatewayRepository gateways;
    private final NetworkSessionRepository sessions;
    private final UsageEventRepository usageEvents;
    private final GatewayCommandRepository commands;

    public GatewayService(
            GatewayRepository gateways,
            NetworkSessionRepository sessions,
            UsageEventRepository usageEvents,
            GatewayCommandRepository commands
    ) {
        this.gateways = gateways;
        this.sessions = sessions;
        this.usageEvents = usageEvents;
        this.commands = commands;
    }

    @Transactional
    public Gateway register(
            String id,
            ApiModels.GatewayRegistrationRequest request
    ) {
        validateId(id, request.gatewayId());

        Gateway gateway = gateways.findById(id)
                .orElseGet(() -> new Gateway(id));

        gateway.register(
                request.hotspotId(),
                request.version(),
                request.hostname(),
                request.platform()
        );

        return gateways.save(gateway);
    }

    @Transactional
    public Gateway heartbeat(
            String id,
            ApiModels.GatewayHeartbeatRequest request
    ) {
        validateId(id, request.gatewayId());

        Gateway gateway = gateways.findById(id)
                .orElseThrow(() -> notFound("Gateway not registered: " + id));

        gateway.heartbeat(
                request.version(),
                request.status(),
                request.hostname()
        );

        return gateways.save(gateway);
    }

    @Transactional(readOnly = true)
    public List<Gateway> list() {
        return gateways.findAll();
    }

    @Transactional(readOnly = true)
    public Gateway get(String id) {
        return gateways.findById(id)
                .orElseThrow(() -> notFound("Gateway not found: " + id));
    }

    @Transactional(readOnly = true)
    public ApiModels.GatewayPolicy policy(String id) {

        Gateway gateway = get(id);

        List<ApiModels.ClientPolicy> clients =
                sessions.findByGatewayIdAndStatusOrderByCreatedAtAsc(
                        id,
                        "ACTIVE"
                )
                .stream()
                .map(s -> new ApiModels.ClientPolicy(
                        s.getId(),
                        s.getUserId(),
                        s.getPlan(),
                        s.getStatus(),
                        s.getSpeedMbps(),
                        s.getSpeedMbps(),
                        (long) s.getQuotaMb() * 1024L * 1024L,
                        (long) s.getUsedMb() * 1024L * 1024L
                ))
                .toList();

        return new ApiModels.GatewayPolicy(
                id,
                gateway.getPolicyVersion(),
                clients
        );
    }

    @Transactional
    public void reportUsage(
            String id,
            ApiModels.UsageReport report
    ) {
        validateId(id, report.gatewayId());
        get(id);

        for (ApiModels.ClientUsage client : report.clients()) {

            NetworkSession session =
                    sessions.findById(client.sessionId())
                            .orElse(null);

            if (session == null
                    || !id.equals(session.getGatewayId())
                    || !"ACTIVE".equals(session.getStatus())) {
                continue;
            }

            long rx = Math.max(0, client.bytesReceived());
            long tx = Math.max(0, client.bytesSent());
            long total = rx + tx;

            session.addUsageBytes(total);
            sessions.save(session);

            usageEvents.save(
                    new com.networkstream.domain.UsageEvent(
                            session.getId(),
                            rx,
                            tx,
                            total,
                            "GATEWAY"
                    )
            );
        }
    }

    @Transactional(readOnly = true)
    public List<ApiModels.GatewayCommand> commands(String id) {

        get(id);

        return commands
                .findByGatewayIdAndAcknowledgedFalseOrderByIdAsc(id)
                .stream()
                .map(c -> new ApiModels.GatewayCommand(
                        String.valueOf(c.getId()),
                        c.getType(),
                        c.getSessionId(),
                        c.getValue()
                ))
                .toList();
    }

    @Transactional
    public void bumpPolicy(String gatewayId) {

        if (gatewayId == null) {
            return;
        }

        gateways.findById(gatewayId)
                .ifPresent(g -> {
                    g.bumpPolicyVersion();
                    gateways.save(g);
                });
    }

    private void validateId(String pathId, String bodyId) {
        if (bodyId == null || !pathId.equals(bodyId)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Gateway ID mismatch"
            );
        }
    }

    private ResponseStatusException notFound(String message) {
        return new ResponseStatusException(
                HttpStatus.NOT_FOUND,
                message
        );
    }
}
