create table if not exists hotspots (
 id varchar(64) primary key, name varchar(160) not null,
 provider_name varchar(160) not null, latitude double precision not null,
 longitude double precision not null, status varchar(32) not null,
 access_type varchar(32) not null, speed_mbps integer not null,
 price_inr integer not null default 0, gateway_id varchar(64),
 created_at timestamp not null default current_timestamp
);
create table if not exists sessions (
 id varchar(64) primary key, user_id varchar(64) not null,
 hotspot_id varchar(64) not null, plan varchar(32) not null,
 status varchar(32) not null, speed_mbps integer not null,
 quota_mb integer not null, used_mb integer not null default 0,
 created_at timestamp not null default current_timestamp, ended_at timestamp
);
create table if not exists gateways (
 id varchar(64) primary key, hotspot_id varchar(64),
 status varchar(32) not null, version varchar(64),
 last_heartbeat timestamp, created_at timestamp not null default current_timestamp
);
create table if not exists usage_events (
 id bigserial primary key, session_id varchar(64) not null,
 bytes_used bigint not null, created_at timestamp not null default current_timestamp
);
