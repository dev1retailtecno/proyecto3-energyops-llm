import json

import httpx

from energyops_mcp.protocol.http_transport import HttpTransport


async def test_multiline_sse_and_session_header():
    seen = []
    def handle(request):
        seen.append(dict(request.headers))
        return httpx.Response(200, headers={"content-type": "text/event-stream", "Mcp-Session-Id": "demo"},
                              text='event: message\ndata: {"jsonrpc":"2.0",\ndata: "id":1,"result":{}}\n\n')
    transport = HttpTransport("https://example.invalid/mcp")
    transport._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        await transport.send('{"jsonrpc":"2.0","id":1,"method":"ping"}')
        assert json.loads(await transport._incoming.get())["id"] == 1
        await transport.send('{"jsonrpc":"2.0","id":2,"method":"ping"}')
        assert seen[1]["mcp-session-id"] == "demo"
    finally:
        await transport.aclose()
