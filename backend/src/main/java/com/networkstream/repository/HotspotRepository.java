package com.networkstream.repository;

import com.networkstream.domain.Hotspot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface HotspotRepository extends JpaRepository<Hotspot, String> {

    List<Hotspot> findAllByOrderByNameAsc();

    Optional<Hotspot> findByGatewayIdAndName(String gatewayId, String name);
}
