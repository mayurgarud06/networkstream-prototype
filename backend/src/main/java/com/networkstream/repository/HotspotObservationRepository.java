package com.networkstream.repository;

import com.networkstream.domain.HotspotObservation;
import org.springframework.data.jpa.repository.JpaRepository;
import java.time.Instant;
import java.util.List;

public interface HotspotObservationRepository extends JpaRepository<HotspotObservation, Long> {
    List<HotspotObservation> findByObservedAtAfterOrderBySignalDbmDesc(Instant after);
}
