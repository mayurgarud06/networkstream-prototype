package com.networkstream.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@SpringBootApplication(scanBasePackages = "com.networkstream")
@EnableJpaRepositories(basePackages = "com.networkstream.repository")
@EntityScan(basePackages = "com.networkstream.domain")
public class NetworkStreamApplication {

    public static void main(String[] args) {
        SpringApplication.run(NetworkStreamApplication.class, args);
    }
}
