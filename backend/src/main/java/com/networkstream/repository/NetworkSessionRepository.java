package com.networkstream.repository;

import com.networkstream.domain.NetworkSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NetworkSessionRepository extends JpaRepository<NetworkSession, String> {

    List<NetworkSession> findByGatewayIdAndStatusOrderByCreatedAtAsc(
            String gatewayId,
            String status
    );
}
