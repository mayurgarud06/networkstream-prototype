package com.networkstream.domain;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "usage_events")
public class UsageEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", nullable = false, length = 64)
    private String sessionId;

    @Column(name = "bytes_received", nullable = false)
    private long bytesReceived;

    @Column(name = "bytes_sent", nullable = false)
    private long bytesSent;

    @Column(name = "bytes_used", nullable = false)
    private long bytesUsed;

    @Column(nullable = false, length = 32)
    private String source;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected UsageEvent() {}

    public UsageEvent(
            String sessionId,
            long bytesReceived,
            long bytesSent,
            long bytesUsed,
            String source
    ) {
        this.sessionId = sessionId;
        this.bytesReceived = bytesReceived;
        this.bytesSent = bytesSent;
        this.bytesUsed = bytesUsed;
        this.source = source;
    }
}
