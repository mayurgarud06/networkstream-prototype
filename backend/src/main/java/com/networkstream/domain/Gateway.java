package com.networkstream.domain;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "gateways")
public class Gateway {

    @Id
    private String id;

    @Column(name = "hotspot_id", length = 64)
    private String hotspotId;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(length = 64)
    private String version;

    @Column(length = 160)
    private String hostname;

    @Column(length = 160)
    private String platform;

    @Column(name = "policy_version", nullable = false)
    private long policyVersion = 1;

    @Column(name = "last_heartbeat")
    private Instant lastHeartbeat;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected Gateway() {}

    public Gateway(String id) {
        this.id = id;
        this.status = "ONLINE";
        this.policyVersion = 1;
        this.lastHeartbeat = Instant.now();
    }

    public String getId() { return id; }
    public String getHotspotId() { return hotspotId; }
    public String getStatus() { return status; }
    public String getVersion() { return version; }
    public String getHostname() { return hostname; }
    public String getPlatform() { return platform; }
    public long getPolicyVersion() { return policyVersion; }
    public Instant getLastHeartbeat() { return lastHeartbeat; }

    public void register(String hotspotId, String version, String hostname, String platform) {
        this.hotspotId = hotspotId;
        this.version = version;
        this.hostname = hostname;
        this.platform = platform;
        this.status = "ONLINE";
        this.lastHeartbeat = Instant.now();
    }

    public void heartbeat(String version, String status, String hostname) {
        this.version = version;
        this.status = status;
        this.hostname = hostname;
        this.lastHeartbeat = Instant.now();
    }

    public void bumpPolicyVersion() {
        this.policyVersion++;
    }
}
