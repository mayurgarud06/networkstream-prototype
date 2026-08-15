package com.networkstream.api;

import java.time.Instant;
import java.util.List;

public final class ApiModels {

    private ApiModels() {}

    public record Hotspot(
            String id,
            String name,
            String providerName,
            double latitude,
            double longitude,
            String status,
            String accessType,
            int speedMbps,
            int priceInr,
            String gatewayId
    ) {}

    public record Session(
            String id,
            String userId,
            String hotspotId,
            String gatewayId,
            String plan,
            String status,
            int speedMbps,
            int quotaMb,
            int usedMb,
            Instant createdAt
    ) {}

    public record ConnectRequest(
            String userId,
            String hotspotId
    ) {}

    public record UsageRequest(
            long bytesUsed
    ) {}

    public record GatewayRegistrationRequest(
            String gatewayId,
            String hotspotId,
            String version,
            String hostname,
            String platform
    ) {}

    public record GatewayHeartbeatRequest(
            String gatewayId,
            String version,
            String status,
            String hostname
    ) {}

    public record GatewayPolicy(
            String gatewayId,
            long version,
            List<ClientPolicy> clients
    ) {}

    public record ClientPolicy(
            String sessionId,
            String userId,
            String plan,
            String status,
            int downloadMbps,
            int uploadMbps,
            long quotaBytes,
            long usedBytes
    ) {}

    public record UsageReport(
            String gatewayId,
            List<ClientUsage> clients
    ) {}

    public record ClientUsage(
            String sessionId,
            long bytesReceived,
            long bytesSent
    ) {}

    public record GatewayCommand(
            String id,
            String type,
            String sessionId,
            String value
    ) {}
}