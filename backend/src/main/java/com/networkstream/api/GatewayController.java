package com.networkstream.api;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/gateways")
@CrossOrigin(origins = "*")
public class GatewayController {

    private final JdbcTemplate jdbc;

    public GatewayController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @PostMapping("/{id}/register")
    public Object register(
            @PathVariable String id,
            @RequestBody ApiModels.GatewayRegistrationRequest r) {

        validateGatewayId(id, r.gatewayId());

        jdbc.update("""
            insert into gateways(
                id, hotspot_id, status, version,
                hostname, platform, last_heartbeat
            )
            values (?, ?, 'ONLINE', ?, ?, ?, ?)
            on conflict(id) do update set
                hotspot_id = excluded.hotspot_id,
                status = excluded.status,
                version = excluded.version,
                hostname = excluded.hostname,
                platform = excluded.platform,
                last_heartbeat = excluded.last_heartbeat
            """,
                id,
                r.hotspotId(),
                r.version(),
                r.hostname(),
                r.platform(),
                Instant.now()
        );

        return getGateway(id);
    }

    @PostMapping("/{id}/heartbeat")
    public Object heartbeat(
            @PathVariable String id,
            @RequestBody ApiModels.GatewayHeartbeatRequest r) {

        validateGatewayId(id, r.gatewayId());

        int updated = jdbc.update("""
            update gateways
            set status = ?,
                version = ?,
                hostname = ?,
                last_heartbeat = ?
            where id = ?
            """,
                r.status(),
                r.version(),
                r.hostname(),
                Instant.now(),
                id
        );

        if (updated == 0) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND,
                    "Gateway is not registered: " + id
            );
        }

        return getGateway(id);
    }

    @GetMapping("/{id}")
    public Object getGateway(@PathVariable String id) {

        try {
            return jdbc.queryForMap("""
                select id,
                       hotspot_id,
                       status,
                       version,
                       hostname,
                       platform,
                       policy_version,
                       last_heartbeat,
                       created_at
                from gateways
                where id = ?
                """, id);
        } catch (Exception e) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND,
                    "Gateway not found: " + id
            );
        }
    }

    @GetMapping("/{id}/policy")
    public ApiModels.GatewayPolicy policy(@PathVariable String id) {

        ensureGatewayExists(id);

        long version = jdbc.queryForObject(
                "select policy_version from gateways where id=?",
                Long.class,
                id
        );

        List<ApiModels.ClientPolicy> clients = jdbc.query("""
            select
                s.id,
                s.user_id,
                s.plan,
                s.status,
                s.speed_mbps,
                s.quota_mb,
                s.used_mb
            from sessions s
            where s.gateway_id = ?
              and s.status = 'ACTIVE'
            order by s.created_at
            """,
                (rs, row) -> new ApiModels.ClientPolicy(
                        rs.getString("id"),
                        rs.getString("user_id"),
                        rs.getString("plan"),
                        rs.getString("status"),
                        rs.getInt("speed_mbps"),
                        rs.getInt("speed_mbps"),
                        rs.getLong("quota_mb") * 1024L * 1024L,
                        rs.getLong("used_mb") * 1024L * 1024L
                ),
                id
        );

        return new ApiModels.GatewayPolicy(id, version, clients);
    }

    @PostMapping("/{id}/usage")
    public String usage(
            @PathVariable String id,
            @RequestBody ApiModels.UsageReport report) {

        validateGatewayId(id, report.gatewayId());

        ensureGatewayExists(id);

        for (ApiModels.ClientUsage client : report.clients()) {

            long total =
                    Math.max(0, client.bytesReceived())
                            + Math.max(0, client.bytesSent());

            jdbc.update("""
                update sessions
                set used_mb = least(
                    quota_mb,
                    used_mb + (? / 1024 / 1024)
                )
                where id = ?
                  and gateway_id = ?
                  and status = 'ACTIVE'
                """,
                    total,
                    client.sessionId()
            );

            jdbc.update("""
                insert into usage_events(
                    session_id,
                    bytes_received,
                    bytes_sent,
                    bytes_used,
                    source
                )
                values (?, ?, ?, ?, 'GATEWAY')
                """,
                    client.sessionId(),
                    Math.max(0, client.bytesReceived()),
                    Math.max(0, client.bytesSent()),
                    total
            );
        }

        return "OK";
    }

    @GetMapping("/{id}/commands")
    public List<ApiModels.GatewayCommand> commands(
            @PathVariable String id) {

        ensureGatewayExists(id);

        return jdbc.query("""
            select
                id,
                type,
                session_id,
                value
            from gateway_commands
            where gateway_id = ?
              and acknowledged = false
            order by id
            """,
                (rs, row) -> new ApiModels.GatewayCommand(
                        String.valueOf(rs.getLong("id")),
                        rs.getString("type"),
                        rs.getString("session_id"),
                        rs.getString("value")
                ),
                id
        );
    }

    private void validateGatewayId(String pathId, String bodyId) {

        if (bodyId == null || !pathId.equals(bodyId)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Gateway ID mismatch"
            );
        }
    }

    private void ensureGatewayExists(String id) {

        Integer count = jdbc.queryForObject(
                "select count(*) from gateways where id=?",
                Integer.class,
                id
        );

        if (count == null || count == 0) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND,
                    "Gateway not found: " + id
            );
        }
    }
}