package com.networkstream.domain;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "sessions")
public class NetworkSession {

    @Id
    private String id;

    @Column(name = "user_id", nullable = false, length = 64)
    private String userId;

    @Column(name = "hotspot_id", nullable = false, length = 64)
    private String hotspotId;

    @Column(name = "gateway_id", length = 64)
    private String gatewayId;

    @Column(nullable = false, length = 32)
    private String plan;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "speed_mbps", nullable = false)
    private int speedMbps;

    @Column(name = "quota_mb", nullable = false)
    private int quotaMb;

    @Column(name = "used_mb", nullable = false)
    private int usedMb;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "ended_at")
    private Instant endedAt;

    protected NetworkSession() {}

    public NetworkSession(
            String id,
            String userId,
            String hotspotId,
            String gatewayId,
            String plan,
            int speedMbps,
            int quotaMb
    ) {
        this.id = id;
        this.userId = userId;
        this.hotspotId = hotspotId;
        this.gatewayId = gatewayId;
        this.plan = plan;
        this.status = "ACTIVE";
        this.speedMbps = speedMbps;
        this.quotaMb = quotaMb;
        this.usedMb = 0;
        this.createdAt = Instant.now();
    }

    public String getId() { return id; }
    public String getUserId() { return userId; }
    public String getHotspotId() { return hotspotId; }
    public String getGatewayId() { return gatewayId; }
    public String getPlan() { return plan; }
    public String getStatus() { return status; }
    public int getSpeedMbps() { return speedMbps; }
    public int getQuotaMb() { return quotaMb; }
    public int getUsedMb() { return usedMb; }
    public Instant getCreatedAt() { return createdAt; }

    public void addUsageBytes(long bytes) {
        if (bytes <= 0) return;
        long mb = bytes / (1024L * 1024L);
        if (mb <= 0) return;
        this.usedMb = (int) Math.min(this.quotaMb, (long) this.usedMb + mb);
    }

    public void upgrade() {
        this.plan = "PREMIUM";
        this.speedMbps = 25;
        this.quotaMb = 5120;
    }

    public void end() {
        this.status = "ENDED";
        this.endedAt = Instant.now();
    }
}
