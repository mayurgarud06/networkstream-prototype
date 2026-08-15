package com.networkstream.domain;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "gateway_commands")
public class GatewayCommand {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "gateway_id", nullable = false, length = 64)
    private String gatewayId;

    @Column(nullable = false, length = 64)
    private String type;

    @Column(name = "session_id", length = 64)
    private String sessionId;

    @Column(length = 255)
    private String value;

    @Column(nullable = false)
    private boolean acknowledged = false;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected GatewayCommand() {}

    public Long getId() { return id; }
    public String getGatewayId() { return gatewayId; }
    public String getType() { return type; }
    public String getSessionId() { return sessionId; }
    public String getValue() { return value; }
    public boolean isAcknowledged() { return acknowledged; }
}
