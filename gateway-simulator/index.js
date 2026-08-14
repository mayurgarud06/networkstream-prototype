const API=process.env.API||"http://localhost:8080";
const gatewayId=process.env.GATEWAY_ID||"GW-A";
async function heartbeat(){
 try{
  const r=await fetch(`${API}/api/gateways/${gatewayId}/heartbeat`,{
   method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({gatewayId,version:"0.2.0-simulator",status:"ONLINE"})
  });
  console.log(new Date().toISOString(),gatewayId,"heartbeat",r.status);
 }catch(e){console.error("heartbeat failed",e.message);}
}
heartbeat();setInterval(heartbeat,10000);
