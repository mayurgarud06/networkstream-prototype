insert into hotspots(id,name,provider_name,latitude,longitude,status,access_type,speed_mbps,price_inr,gateway_id)
values
('HS-A','Neighbour A Wi-Fi','Neighbour A',20.7050,77.0200,'ONLINE','FREE',20,0,'GW-A'),
('HS-B','Neighbour B Wi-Fi','Neighbour B',20.7070,77.0230,'ONLINE','FREE',30,0,'GW-B'),
('HS-C','Premium Pilot Wi-Fi','Pilot Provider',20.7090,77.0260,'ONLINE','PREMIUM',100,10,'GW-C')
on conflict(id) do nothing;
