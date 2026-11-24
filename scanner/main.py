import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://localhost:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(init.protocol_version, init.server_info)

            tools = await session.list_tools()
            for t in tools.tools:
                print(t.name, "|", t.description)


asyncio.run(main())


# initialize	Handshake: "who are you, and what do you support?"	Server name, version, protocol version, capabilities
# tools/list	"What tools do you offer?"	Tool names, descriptions, input schemas
# resources/list	"What data can I read?"	Resource URIs, names, descriptions
# prompts/list	"What prompt templates do you have?"	Prompt names, descriptions, arguments
# 
# 
# init.protocol_version    # protocol version the server agreed to
# init.server_info         # name and version of the server
# init.capabilities        # which features it supports (tools, resources, prompts)
# init.instructions        # optional text from the server, may be None
