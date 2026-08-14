package com.networkstream.api;
import java.time.Instant;
public final class ApiModels {
 private ApiModels(){}
 public record Hotspot(String id,String name,String providerName,double latitude,double longitude,String status,String accessType,int speedMbps,int priceInr,String gatewayId){}
 public record Session(String id,String userId,String hotspotId,String plan,String status,int speedMbps,int quotaMb,int usedMb,Instant createdAt){}
 public record ConnectRequest(String userId,String hotspotId,String plan){}
 public record UsageRequest(int mb){}
 public record GatewayHeartbeatRequest(String gatewayId,String version,String status){}
}
