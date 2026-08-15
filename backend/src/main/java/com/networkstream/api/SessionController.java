package com.networkstream.api;

import com.networkstream.service.SessionService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/sessions")
@CrossOrigin(origins = "*")
public class SessionController {

    private final SessionService service;

    public SessionController(SessionService service) {
        this.service = service;
    }

    @PostMapping
    public ApiModels.Session connect(
            @RequestBody ApiModels.ConnectRequest request
    ) {
        return service.connect(request);
    }

    @PostMapping("/{id}/usage")
    public ApiModels.Session usage(
            @PathVariable String id,
            @RequestBody ApiModels.UsageRequest request
    ) {
        return service.usage(id, request);
    }

    @PostMapping("/{id}/upgrade")
    public ApiModels.Session upgrade(@PathVariable String id) {
        return service.upgrade(id);
    }

    @PostMapping("/{id}/end")
    public ApiModels.Session end(@PathVariable String id) {
        return service.end(id);
    }

    @GetMapping("/{id}")
    public ApiModels.Session get(@PathVariable String id) {
        return service.get(id);
    }
}
