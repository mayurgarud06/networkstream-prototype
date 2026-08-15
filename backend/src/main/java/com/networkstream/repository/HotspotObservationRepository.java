package com.networkstream.repository;

import com.networkstream.domain.HotspotObservation;
import org.springframework.data.jpa.repository.JpaRepository;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

public interface HotspotObservationRepository extends JpaRepository<HotspotObservation, Long> {
    List<HotspotObservation> findByObservedAtAfterOrderBySignalDbmDesc(Instant after);

    Optional<HotspotObservation> findFirstByGatewayIdAndBssid(String gatewayId, String bssid);

    Optional<HotspotObservation> findFirstByGatewayIdAndSsidAndBssidIsNull(String gatewayId, String ssid);
}
