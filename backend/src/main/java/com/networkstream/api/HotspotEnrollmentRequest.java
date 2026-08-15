package com.networkstream.api;

public record HotspotEnrollmentRequest(
        String ssid,
        String bssid,
        String providerName,
        double latitude,
        double longitude,
        String accessType,
        int speedMbps,
        int priceInr,
        String gatewayId
) {}
