import socket
import asyncio
import httpx

original_getaddrinfo = socket.getaddrinfo

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "api.telegram.org":
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('149.154.166.110', port))]
    return original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

async def test():
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.telegram.org/")
        print("Success:", resp.status_code)

asyncio.run(test())