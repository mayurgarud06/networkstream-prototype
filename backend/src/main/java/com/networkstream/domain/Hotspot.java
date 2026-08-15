package com.networkstream.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "hotspots")
public class Hotspot {

    @Id
    private String id;

    @Column(nullable = false, length = 160)
    private String name;

    @Column(name = "provider_name", nullable = false, length = 160)
    private String providerName;

    @Column(nullable = false)
    private double latitude;

    @Column(nullable = false)
    private double longitude;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "access_type", nullable = false, length = 32)
    private String accessType;

    @Column(name = "speed_mbps", nullable = false)
    private int speedMbps;

    @Column(name = "price_inr", nullable = false)
    private int priceInr;

    @Column(name = "gateway_id", length = 64)
    private String gatewayId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected Hotspot() {}

    public Hotspot(String id, String name, String providerName, double latitude, double longitude,
                   String status, String accessType, int speedMbps, int priceInr, String gatewayId) {
        this.id = id;
        this.name = name;
        this.providerName = providerName;
        this.latitude = latitude;
        this.longitude = longitude;
        this.status = status;
        this.accessType = accessType;
        this.speedMbps = speedMbps;
        this.priceInr = priceInr;
        this.gatewayId = gatewayId;
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public String getProviderName() { return providerName; }
    public double getLatitude() { return latitude; }
    public double getLongitude() { return longitude; }
    public String getStatus() { return status; }
    public String getAccessType() { return accessType; }
    public int getSpeedMbps() { return speedMbps; }
    public int getPriceInr() { return priceInr; }
    public String getGatewayId() { return gatewayId; }
}