#!/usr/bin/env python3

import argparse
import json
import platform
import socket
import subprocess
import time
import urllib.request


VERSION = "0.3.0-linux-agent"


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False
    )


def post_json(url, payload):
    data = json.dumps(payload).encode()

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode()

        if not body:
            return None

        return json.loads(body)


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode()

        if not body:
            return None

        return json.loads(body)


def discover_interfaces():

    result = run(["ip", "-j", "addr"])

    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def discover_routes():

    result = run(["ip", "-j", "route"])

    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def discover_network():

    return {
        "interfaces": discover_interfaces(),
        "routes": discover_routes()
    }


def register(api, gateway_id, hotspot_id):

    payload = {
        "gatewayId": gateway_id,
        "hotspotId": hotspot_id,
        "version": VERSION,
        "hostname": socket.gethostname(),
        "platform": platform.platform()
    }

    return post_json(
        f"{api}/api/gateways/{gateway_id}/register",
        payload
    )


def heartbeat(api, gateway_id):

    payload = {
        "gatewayId": gateway_id,
        "version": VERSION,
        "status": "ONLINE",
        "hostname": socket.gethostname()
    }

    return post_json(
        f"{api}/api/gateways/{gateway_id}/heartbeat",
        payload
    )


def get_policy(api, gateway_id):

    return get_json(
        f"{api}/api/gateways/{gateway_id}/policy"
    )


def get_commands(api, gateway_id):

    return get_json(
        f"{api}/api/gateways/{gateway_id}/commands"
    )


def print_network():

    print("NetworkStream network inspection")

    network = discover_network()

    print(
        json.dumps(
            network,
            indent=2
        )
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--api",
        default="http://127.0.0.1:8080"
    )

    parser.add_argument(
        "--gateway-id",
        default=socket.gethostname()
    )

    parser.add_argument(
        "--hotspot-id",
        default="HS-A"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    parser.add_argument(
        "--once",
        action="store_true"
    )

    args = parser.parse_args()

    print("NetworkStream Linux Gateway Agent")
    print("version:", VERSION)
    print("platform:", platform.platform())
    print("gateway:", args.gateway_id)

    if args.dry_run:

        print()
        print("DRY RUN")
        print("No routing/firewall changes will be made.")
        print()

        print_network()

    try:

        print(
            "register:",
            register(
                args.api,
                args.gateway_id,
                args.hotspot_id
            )
        )

    except Exception as error:

        print(
            "registration failed:",
            error
        )

    while True:

        try:

            print(
                "heartbeat:",
                heartbeat(
                    args.api,
                    args.gateway_id
                )
            )

            policy = get_policy(
                args.api,
                args.gateway_id
            )

            print(
                "policy:",
                json.dumps(
                    policy,
                    indent=2
                )
            )

            commands = get_commands(
                args.api,
                args.gateway_id
            )

            print(
                "commands:",
                json.dumps(
                    commands,
                    indent=2
                )
            )

        except Exception as error:

            print(
                "gateway communication failed:",
                error
            )

        if args.once:
            break

        time.sleep(10)


if __name__ == "__main__":
    main()