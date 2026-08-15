package com.networkstream.repository;

import com.networkstream.domain.GatewayCommand;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface GatewayCommandRepository extends JpaRepository<GatewayCommand, Long> {

    List<GatewayCommand> findByGatewayIdAndAcknowledgedFalseOrderByIdAsc(
            String gatewayId
    );
}
