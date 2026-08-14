package com.networkstream.api;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.UUID;
@RestController @RequestMapping("/api/sessions") @CrossOrigin(origins="*")
public class SessionController {
 private final JdbcTemplate jdbc;
 public SessionController(JdbcTemplate jdbc){this.jdbc=jdbc;}

 @PostMapping public ApiModels.Session connect(@RequestBody ApiModels.ConnectRequest r){
  var h=jdbc.queryForMap("select speed_mbps from hotspots where id=?",r.hotspotId());
  String plan=r.plan()==null?"FREE":r.plan().toUpperCase();
  int base=((Number)h.get("speed_mbps")).intValue();
  int speed=plan.equals("PREMIUM")?Math.max(25,base):Math.min(5,base);
  int quota=plan.equals("PREMIUM")?5120:500;
  String id="SES-"+UUID.randomUUID();
  jdbc.update("insert into sessions(id,user_id,hotspot_id,plan,status,speed_mbps,quota_mb) values(?,?,?,?,?,?,?)",id,r.userId(),r.hotspotId(),plan,"ACTIVE",speed,quota);
  return get(id);
 }

 @PostMapping("/{id}/usage") public ApiModels.Session usage(@PathVariable String id,@RequestBody ApiModels.UsageRequest r){
  int mb=Math.max(0,r.mb());
  jdbc.update("update sessions set used_mb=least(quota_mb,used_mb+?) where id=?",mb,id);
  jdbc.update("insert into usage_events(session_id,bytes_used) values(?,?)",id,mb*1024L*1024L);
  return get(id);
 }

 @PostMapping("/{id}/upgrade") public ApiModels.Session upgrade(@PathVariable String id){
  jdbc.update("update sessions set plan='PREMIUM',speed_mbps=25,quota_mb=5120 where id=?",id); return get(id);
 }
 @PostMapping("/{id}/end") public ApiModels.Session end(@PathVariable String id){
  jdbc.update("update sessions set status='ENDED',ended_at=current_timestamp where id=?",id); return get(id);
 }
 @GetMapping("/{id}") public ApiModels.Session get(@PathVariable String id){
  return jdbc.queryForObject("select id,user_id,hotspot_id,plan,status,speed_mbps,quota_mb,used_mb,created_at from sessions where id=?",
   (rs,row)->new ApiModels.Session(rs.getString("id"),rs.getString("user_id"),rs.getString("hotspot_id"),rs.getString("plan"),rs.getString("status"),rs.getInt("speed_mbps"),rs.getInt("quota_mb"),rs.getInt("used_mb"),rs.getTimestamp("created_at").toInstant()),id);
 }
}
