package com.networkstream.api;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.time.Instant;
@RestController @RequestMapping("/api/gateways") @CrossOrigin(origins="*")
public class GatewayController {
 private final JdbcTemplate jdbc;
 public GatewayController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 @PostMapping("/{id}/heartbeat")
 public String heartbeat(@PathVariable String id,@RequestBody ApiModels.GatewayHeartbeatRequest r){
  jdbc.update("insert into gateways(id,status,version,last_heartbeat) values(?,?,?,?) on conflict(id) do update set status=excluded.status,version=excluded.version,last_heartbeat=excluded.last_heartbeat",
   id,r.status(),r.version(),Instant.now()); return "OK";
 }
 @GetMapping("/{id}") public Object get(@PathVariable String id){
  return jdbc.queryForMap("select id,hotspot_id,status,version,last_heartbeat,created_at from gateways where id=?",id);
 }
}
