from __future__ import annotations

from collections.abc import Callable
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from fastapi import Request

TrustedProxyNetwork = IPv4Network | IPv6Network


def parse_trusted_proxy_networks(cidrs: list[str]) -> list[TrustedProxyNetwork]:
    networks: list[TrustedProxyNetwork] = []
    for raw in cidrs:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            network = ip_network(value, strict=False)
        except ValueError as exc:
            raise RuntimeError(f"Invalid TRUSTED_PROXY_CIDRS entry: {value}") from exc
        if isinstance(network, (IPv4Network, IPv6Network)):
            networks.append(network)
    return networks


def remote_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_trusted_proxy(remote_ip_value: str, trusted_proxy_networks: list[TrustedProxyNetwork]) -> bool:
    if not trusted_proxy_networks:
        return False
    try:
        remote_addr = ip_address(remote_ip_value)
    except ValueError:
        return False
    return any(remote_addr in network for network in trusted_proxy_networks)


def client_key(
    request: Request,
    *,
    trusted_proxy_networks: list[TrustedProxyNetwork],
    remote_ip_resolver: Callable[[Request], str] = remote_ip,
) -> str:
    resolved_remote_ip = remote_ip_resolver(request)
    if not is_trusted_proxy(resolved_remote_ip, trusted_proxy_networks):
        return resolved_remote_ip

    forwarded_for = request.headers.get("X-Forwarded-For")
    if not forwarded_for:
        return resolved_remote_ip

    first_hop = forwarded_for.split(",")[0].strip()
    if not first_hop:
        return resolved_remote_ip
    try:
        ip_address(first_hop)
        return first_hop
    except ValueError:
        return resolved_remote_ip
