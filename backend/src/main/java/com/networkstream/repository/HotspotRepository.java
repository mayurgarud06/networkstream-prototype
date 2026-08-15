package com.networkstream.repository;

import com.networkstream.domain.Hotspot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface HotspotRepository extends JpaRepository<Hotspot, String> {

    List<Hotspot> findAllByOrderByNameAsc();
}
