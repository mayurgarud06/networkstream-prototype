package com.networkstream.api;

import com.networkstream.service.HotspotService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/hotspots")
@CrossOrigin(origins = "*")
public class HotspotController {

    private final HotspotService service;

    public HotspotController(HotspotService service) {
        this.service = service;
    }

    @GetMapping
    public List<ApiModels.Hotspot> list() {
        return service.list();
    }
}
