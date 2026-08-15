package com.networkstream.api;

import com.networkstream.service.HotspotObservationService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/hotspots")
@CrossOrigin(origins = "*")
public class HotspotObservationController {
    private final HotspotObservationService service;

    public HotspotObservationController(HotspotObservationService service) {
        this.service = service;
    }

    @GetMapping("/observed")
    public List<ApiModels.HotspotObservation> observed(@RequestParam(defaultValue = "120") int seconds) {
        return service.recent(seconds);
    }
}
