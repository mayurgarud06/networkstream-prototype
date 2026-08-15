package com.networkstream.api;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.List;
@RestController @RequestMapping("/api/hotspots") @CrossOrigin(origins="*")
public class HotspotController {
 private final JdbcTemplate jdbc;
 public HotspotController(JdbcTemplate jdbc){this.jdbc=jdbc;}
    @GetMapping
    public List<ApiModels.Hotspot> list() {

        return jdbc.query("""
        select
            h.id,
            h.name,
            h.provider_name,
            h.latitude,
            h.longitude,
            case
                when g.status = 'ONLINE'
                 and g.last_heartbeat >
                     current_timestamp - interval '30 seconds'
                then 'ONLINE'
                else 'OFFLINE'
            end as status,
            h.access_type,
            h.speed_mbps,
            h.price_inr,
            h.gateway_id
        from hotspots h
        left join gateways g
            on g.id = h.gateway_id
        order by h.name
        """,
                (rs, row) ->
                        new ApiModels.Hotspot(
                                rs.getString("id"),
                                rs.getString("name"),
                                rs.getString("provider_name"),
                                rs.getDouble("latitude"),
                                rs.getDouble("longitude"),
                                rs.getString("status"),
                                rs.getString("access_type"),
                                rs.getInt("speed_mbps"),
                                rs.getInt("price_inr"),
                                rs.getString("gateway_id")
                        )
        );
    }
}
