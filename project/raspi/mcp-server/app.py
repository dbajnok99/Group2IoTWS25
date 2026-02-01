import contextlib

from collections.abc import AsyncIterator



import uvicorn

import mcp.types as types



from mcp.server.lowlevel import Server

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager



from starlette.applications import Starlette

from starlette.routing import Mount

from starlette.types import Scope, Receive, Send




# --- MCP server ---

mcp_server = Server("starlette-mcp")



@mcp_server.list_tools()

async def list_tools() -> list[types.Tool]:

 return [

 types.Tool(

 name="add",

 description="Add two integers: a + b",

 inputSchema={

 "type": "object",

 "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},

 "required": ["a", "b"],

 },

 )

 ]



@mcp_server.call_tool()

async def call_tool(name: str, arguments: dict):

 if name != "add":

    raise ValueError(f"Unknown tool: {name}")

 res = int(arguments["a"]) + int(arguments["b"])

 return [types.TextContent(type="text", text=str(res))]




# --- Streamable HTTP manager ---

session_manager = StreamableHTTPSessionManager(

 app=mcp_server,

 event_store=None,

 json_response=True,

 stateless=True,

)




# Mount MCP as a pure ASGI app at /mcp

async def mcp_asgi(scope: Scope, receive: Receive, send: Send) -> None:

 await session_manager.handle_request(scope, receive, send)




@contextlib.asynccontextmanager

async def lifespan(app: Starlette) -> AsyncIterator[None]:

 async with session_manager.run():

    yield




app = Starlette(

 debug=True,

 routes=[Mount("/mcp", app=mcp_asgi)],

 lifespan=lifespan,

)




if __name__ == "__main__":

 uvicorn.run("app:app", host="127.0.0.1", port=4200, reload=True)