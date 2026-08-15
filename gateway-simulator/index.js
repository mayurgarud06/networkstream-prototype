const API = process.env.API || "http://localhost:8080";
const gatewayId = process.env.GATEWAY_ID || "GW-A";
const hotspotId = process.env.HOTSPOT_ID || "HS-A";

const VERSION = "0.3.0-simulator";

async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const text = await response.text();

    let body = null;

    try {
        body = text ? JSON.parse(text) : null;
    } catch {
        body = text;
    }

    if (!response.ok) {
        throw new Error(
            `${response.status}: ${JSON.stringify(body)}`
        );
    }

    return body;
}

async function register() {

    return request(
        `/api/gateways/${gatewayId}/register`,
        {
            method: "POST",
            body: JSON.stringify({
                gatewayId,
                hotspotId,
                version: VERSION,
                hostname: `sim-${gatewayId}`,
                platform: "networkstream-simulator"
            })
        }
    );
}

async function heartbeat() {

    return request(
        `/api/gateways/${gatewayId}/heartbeat`,
        {
            method: "POST",
            body: JSON.stringify({
                gatewayId,
                version: VERSION,
                status: "ONLINE",
                hostname: `sim-${gatewayId}`
            })
        }
    );
}

async function policy() {

    return request(
        `/api/gateways/${gatewayId}/policy`
    );
}

async function commands() {

    return request(
        `/api/gateways/${gatewayId}/commands`
    );
}

async function cycle() {

    try {

        const gateway = await heartbeat();

        const currentPolicy = await policy();

        const pendingCommands = await commands();

        console.log(
            new Date().toISOString(),
            gatewayId,
            {
                heartbeat: gateway,
                policyVersion: currentPolicy?.policyVersion,
                clients: currentPolicy?.clients?.length || 0,
                commands: pendingCommands?.length || 0
            }
        );

    } catch (error) {

        console.error(
            new Date().toISOString(),
            gatewayId,
            "gateway cycle failed:",
            error.message
        );
    }
}

async function main() {

    try {

        console.log(
            "Registering gateway:",
            gatewayId
        );

        console.log(
            await register()
        );

    } catch (error) {

        console.error(
            "registration failed:",
            error.message
        );
    }

    await cycle();

    setInterval(cycle, 10000);
}

main();