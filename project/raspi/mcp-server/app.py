import contextlib
import sqlite3
import uvicorn
import mcp.types as types
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Scope, Receive, Send

from .. import ingestor

# --- MCP server ---
mcp_server = Server("starlette-mcp")
DB_NAME = "../sensor_data.db"
def db():
    return sqlite3.connect(DB_NAME)


@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    empty_schema = {"type": "object", "properties": {}}

    return [
        types.Tool(
            name="sensors.list",
            description="List available sensors",
            inputSchema=empty_schema,
        ),
        types.Tool(
            name="sensors.latest",
            description="Get the latest value of a sensor",
            inputSchema={
                "type": "object",
                "properties": {"sensor_id": {"type": "string"}},
                "required": ["sensor_id"],
            },
        ),
        types.Tool(
            name="sensors.query",
            description="Query sensor values for a time window",
            inputSchema={
                "type": "object",
                "properties": {
                    "sensor_id": {"type": "string"},
                    "window_seconds": {"type": "integer"},
                },
                "required": ["sensor_id", "window_seconds"],
            },
        ),
        types.Tool(
            name="actuators.set",
            description="Set an actuator value",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "actuator": {"type": "string"},
                    "value": {"type": "boolean"},
                },
                "required": ["device_id", "actuator", "value"],
            },
        ),
        types.Tool(
            name="system.status",
            description="Get system status",
            inputSchema=empty_schema,
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    conn = db()
    cur = conn.cursor()

    if name == "sensors.list":
        cur.execute("SELECT DISTINCT sensor FROM readings")
        sensors = [r[0] for r in cur.fetchall()]
        return [types.TextContent(type="text", text=str(sensors))]

    if name == "sensors.latest":
        sensor = arguments["sensor_id"]
        cur.execute(
            "SELECT value, timestamp FROM readings WHERE sensor=? ORDER BY timestamp DESC LIMIT 1",
            (sensor,),
        )
        row = cur.fetchone()
        return [types.TextContent(type="text", text=str(row))]

    if name == "sensors.query":
        sensor = arguments["sensor_id"]
        window = int(arguments["window_seconds"])
        since = datetime.now() - timedelta(seconds=window)

        cur.execute(
            "SELECT value, timestamp FROM readings WHERE sensor=? AND timestamp>=?",
            (sensor, since),
        )
        rows = cur.fetchall()
        return [types.TextContent(type="text", text=str(rows))]

    if name == "actuators.set":
        if arguments["device_id"] == "ESP32" and arguments["actuator"] == "LED":
            ingestor.set_esp32_led(arguments["value"])
            return [types.TextContent(type="text", text="OK")]

    if name == "system.status":
        now = datetime.now()
        status = {
            "database_up:": False,
            "thingy32_up:": False,
            "esp32_up:": False,
            "details": {},
            "timestamp": now.isoformat(),
        }

        try:
            cur.execute("SELECT COUNT(*) FROM readings")
            total = cur.fetchone()[0]
            status["database_up"] = True

            cur.execute("SELECT MAX(timestamp) FROM readings WHERE device='Thingy'")
            last_thingy = cur.fetchone()[0]
            if last_thingy:
                delta = now - datetime.fromisoformat(last_thingy)
                status["thingy32_up"] = delta.total_seconds() < 10

            cur.execute("SELECT MAX(timestamp) FROM readings WHERE device='ESP32'")
            last_esp = cur.fetchone()[0]
            if last_esp:
                delta = now - datetime.fromisoformat(last_esp)
                status["esp32_up"] = delta.total_seconds() < 10

        except Exception as e:
            status["details"]["error"] = str(e)

        status["system_up"] = (
            status["database_up"]
            and status["thingy32_up"]
            and status["esp32_up"]
        )

        return [
            types.TextContent(
                type="text",
                text=str(status),
            )
        ]

    raise ValueError("Unknown tool")


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
    uvicorn.run("app:app", host="0.0.0.0", port=4200, reload=True)
