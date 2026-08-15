package com.networkstream.api;

import com.networkstream.service.GatewayService;
import com.networkstream.service.HotspotObservationService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/gateways")
@CrossOrigin(origins = "*")
public class GatewayController {
    private final GatewayService service;
    private final HotspotObservationService observations;

    public GatewayController(GatewayService service, HotspotObservationService observations) {
        this.service = service;
        this.observations = observations;
    }

    @PostMapping("/{id}/register")
    public Object register(@PathVariable String id, @RequestBody ApiModels.GatewayRegistrationRequest request) { return service.register(id, request); }

    @PostMapping("/{id}/heartbeat")
    public Object heartbeat(@PathVariable String id, @RequestBody ApiModels.GatewayHeartbeatRequest request) { return service.heartbeat(id, request); }

    @GetMapping
    public List<com.networkstream.domain.Gateway> list() { return service.list(); }

    @GetMapping("/{id}")
    public Object get(@PathVariable String id) { return service.get(id); }

    @GetMapping("/{id}/policy")
    public ApiModels.GatewayPolicy policy(@PathVariable String id) { return service.policy(id); }

    @PostMapping("/{id}/usage")
    public String usage(@PathVariable String id, @RequestBody ApiModels.UsageReport report) { service.reportUsage(id, report); return "OK"; }

    @PostMapping("/{id}/scan")
    public ApiModels.GatewayScanResponse scan(@PathVariable String id, @RequestBody ApiModels.HotspotScanReport report) {
        observations.report(id, report);
        return new ApiModels.GatewayScanResponse("OK");
    }

    @GetMapping("/{id}/commands")
    public Object commands(@PathVariable String id) { return service.commands(id); }

    @PostMapping("/{id}/commands")
    public ApiModels.GatewayCommand enqueueCommand(@PathVariable String id, @RequestBody ApiModels.GatewayCommand command) {
        return service.enqueueCommand(id, command.type(), command.sessionId(), command.value());
    }

    @PostMapping("/{id}/commands/{commandId}/ack")
    public String acknowledgeCommand(@PathVariable String id, @PathVariable Long commandId) {
        service.acknowledgeCommand(id, commandId);
        return "OK";
    }

    @PostMapping("/{id}/telemetry")
    public String telemetry(@PathVariable String id, @RequestBody ApiModels.GatewayTelemetry report) {
        service.reportTelemetry(id, report);
        return "OK";
    }

    @GetMapping("/{id}/telemetry")
    public ApiModels.GatewayTelemetry telemetry(@PathVariable String id) { return service.telemetry(id); }
}
