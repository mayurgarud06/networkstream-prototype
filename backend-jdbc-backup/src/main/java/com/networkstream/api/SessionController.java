package com.networkstream.api;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/sessions")
@CrossOrigin(origins = "*")
public class SessionController {

    private final JdbcTemplate jdbc;

    public SessionController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @PostMapping
    public ApiModels.Session connect(
            @RequestBody ApiModels.ConnectRequest r) {

        var h = jdbc.queryForMap("""
            select speed_mbps, gateway_id
            from hotspots
            where id = ?
            """,
                r.hotspotId()
        );

        int baseSpeed =
                ((Number) h.get("speed_mbps")).intValue();

        String gatewayId =
                (String) h.get("gateway_id");

        String plan = "FREE";

        int speed = Math.min(5, baseSpeed);
        int quota = 500;

        String id = "SES-" + UUID.randomUUID();

        jdbc.update("""
            insert into sessions(
                id,
                user_id,
                hotspot_id,
                gateway_id,
                plan,
                status,
                speed_mbps,
                quota_mb
            )
            values (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
                id,
                r.userId(),
                r.hotspotId(),
                gatewayId,
                plan,
                speed,
                quota
        );

        bumpPolicyVersion(gatewayId);

        return get(id);
    }

    @PostMapping("/{id}/usage")
    public ApiModels.Session usage(
            @PathVariable String id,
            @RequestBody ApiModels.UsageRequest r) {

        long bytes = Math.max(0, r.bytesUsed());

        jdbc.update("""
            update sessions
            set used_mb = least(
                quota_mb,
                used_mb + (? / 1024 / 1024)
            )
            where id = ?
              and status = 'ACTIVE'
            """,
                bytes,
                id
        );

        jdbc.update("""
            insert into usage_events(
                session_id,
                bytes_received,
                bytes_sent,
                bytes_used,
                source
            )
            values (?, 0, 0, ?, 'SIMULATOR')
            """,
                id,
                bytes
        );

        return get(id);
    }

    @PostMapping("/{id}/upgrade")
    public ApiModels.Session upgrade(
            @PathVariable String id) {

        var gateway = jdbc.queryForMap("""
            select gateway_id
            from sessions
            where id = ?
            """, id);

        String gatewayId =
                (String) gateway.get("gateway_id");

        jdbc.update("""
            update sessions
            set plan = 'PREMIUM',
                speed_mbps = 25,
                quota_mb = 5120
            where id = ?
              and status = 'ACTIVE'
            """,
                id
        );

        bumpPolicyVersion(gatewayId);

        return get(id);
    }

    @PostMapping("/{id}/end")
    public ApiModels.Session end(
            @PathVariable String id) {

        var gateway = jdbc.queryForMap("""
            select gateway_id
            from sessions
            where id = ?
            """, id);

        String gatewayId =
                (String) gateway.get("gateway_id");

        jdbc.update("""
            update sessions
            set status = 'ENDED',
                ended_at = current_timestamp
            where id = ?
            """,
                id
        );

        bumpPolicyVersion(gatewayId);

        return get(id);
    }

    @GetMapping("/{id}")
    public ApiModels.Session get(
            @PathVariable String id) {

        return jdbc.queryForObject("""
            select
                id,
                user_id,
                hotspot_id,
                gateway_id,
                plan,
                status,
                speed_mbps,
                quota_mb,
                used_mb,
                created_at
            from sessions
            where id = ?
            """,
                (rs, row) -> new ApiModels.Session(
                        rs.getString("id"),
                        rs.getString("user_id"),
                        rs.getString("hotspot_id"),
                        rs.getString("gateway_id"),
                        rs.getString("plan"),
                        rs.getString("status"),
                        rs.getInt("speed_mbps"),
                        rs.getInt("quota_mb"),
                        rs.getInt("used_mb"),
                        rs.getTimestamp("created_at").toInstant()
                ),
                id
        );
    }

    private void bumpPolicyVersion(String gatewayId) {

        if (gatewayId == null) {
            return;
        }

        jdbc.update("""
            update gateways
            set policy_version = policy_version + 1
            where id = ?
            """,
                gatewayId
        );
    }
}