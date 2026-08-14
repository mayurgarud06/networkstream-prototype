package com.networkstream.api;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.List;
@RestController @RequestMapping("/api/hotspots") @CrossOrigin(origins="*")
public class HotspotController {
 private final JdbcTemplate jdbc;
 public HotspotController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 @GetMapping public List<ApiModels.Hotspot> list(){
  return jdbc.query("select id,name,provider_name,latitude,longitude,status,access_type,speed_mbps,price_inr,gateway_id from hotspots order by name",
   (rs,row)->new ApiModels.Hotspot(rs.getString("id"),rs.getString("name"),rs.getString("provider_name"),rs.getDouble("latitude"),rs.getDouble("longitude"),rs.getString("status"),rs.getString("access_type"),rs.getInt("speed_mbps"),rs.getInt("price_inr"),rs.getString("gateway_id")));
 }
}
