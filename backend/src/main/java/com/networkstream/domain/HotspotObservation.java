package com.networkstream.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "hotspot_observations", indexes = {
        @Index(name = "idx_hotspot_observation_gateway", columnList = "gateway_id"),
        @Index(name = "idx_hotspot_observation_seen", columnList = "observed_at")
})
public class HotspotObservation {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "gateway_id", nullable = false, length = 64)
    private String gatewayId;

    @Column(nullable = false, length = 160)
    private String ssid;

    @Column(length = 64)
    private String bssid;

    @Column(name = "signal_dbm")
    private Integer signalDbm;

    @Column(name = "signal_percent")
    private Integer signalPercent;

    @Column(length = 32)
    private String frequency;

    @Column(length = 64)
    private String security;

    @Column(name = "observed_at", nullable = false)
    private Instant observedAt = Instant.now();

    protected HotspotObservation() {}

    public HotspotObservation(String gatewayId, String ssid, String bssid, Integer signalDbm,
                              String frequency, String security, Instant observedAt) {
        this(gatewayId, ssid, bssid, signalDbm, frequency, security, observedAt, null);
    }

    public HotspotObservation(String gatewayId, String ssid, String bssid, Integer signalDbm,
                              String frequency, String security, Instant observedAt, Integer signalPercent) {
        this.gatewayId = gatewayId;
        this.ssid = ssid;
        this.bssid = bssid;
        this.signalDbm = signalDbm;
        this.signalPercent = signalPercent;
        this.frequency = frequency;
        this.security = security;
        this.observedAt = observedAt == null ? Instant.now() : observedAt;
    }

    public Long getId() { return id; }
    public String getGatewayId() { return gatewayId; }
    public String getSsid() { return ssid; }
    public String getBssid() { return bssid; }
    public Integer getSignalDbm() { return signalDbm; }
    public Integer getSignalPercent() { return signalPercent; }
    public String getFrequency() { return frequency; }
    public String getSecurity() { return security; }
    public Instant getObservedAt() { return observedAt; }

    public void updateObservation(String ssid, String bssid, Integer signalDbm,
                                  String frequency, String security, Instant observedAt) {
        updateObservation(ssid, bssid, signalDbm, null, frequency, security, observedAt);
    }

    public void updateObservation(String ssid, String bssid, Integer signalDbm, Integer signalPercent,
                                  String frequency, String security, Instant observedAt) {
        this.ssid = ssid;
        this.bssid = bssid;
        this.signalDbm = signalDbm;
        this.signalPercent = signalPercent;
        this.frequency = frequency;
        this.security = security;
        this.observedAt = observedAt == null ? Instant.now() : observedAt;
    }
}
