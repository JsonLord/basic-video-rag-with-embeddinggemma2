"""Resolve public destinations at connect time, preserving TLS hostname checks.

Direct HTTPS connects to a validated literal IP (Host and TLS SNI stay original).
A configured environment proxy remains the sole outbound path; its administrator
must also enforce public-only destination resolution inside that proxy.
"""
import asyncio
import ipaddress
import socket
from urllib.request import getproxies, proxy_bypass

import httpx

async def public_addresses(host: str, timeout: float = 5):
    records = await asyncio.wait_for(
        asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM), timeout)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('non-public destination')
    return addresses

class PublicAddressTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner=None):
        self.inner = inner or httpx.AsyncHTTPTransport(trust_env=True)

    async def handle_async_request(self, request):
        host = request.url.host
        try:
            addresses = await public_addresses(host)
        except TimeoutError:
            raise httpx.ConnectTimeout('destination lookup timed out') from None
        except (OSError, ValueError):
            raise httpx.ConnectError('destination denied') from None
        request.headers['Host'] = host
        request.extensions['sni_hostname'] = host
        request.url = request.url.copy_with(host=addresses[0])
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()

def proxy_for(base: str):
    host = httpx.URL(base).host
    proxies = getproxies()
    return None if proxy_bypass(host) else proxies.get('https', proxies.get('all'))

def transport_for(base: str):
    proxy = proxy_for(base)
    if proxy:
        # Keep injected authentication and the trusted platform egress path.
        return httpx.AsyncHTTPTransport(proxy=proxy, trust_env=True)
    return PublicAddressTransport()
