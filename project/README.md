# IoT Sensor Network with MCP & LLM Agent

This project implements a sensor data ingestion system using a Raspberry Pi as a central hub. It collects data from an **ESP32** (via Wi-Fi/HTTP) and a **Thingy:53** (via Bluetooth Low Energy), exposes them through a **Model Context Protocol (MCP)** server, and allows an **LLM Agent** to monitor and control the hardware.

## Project Structure

```text
project/
├── client/
│   └── agent_client.py       # LLM Agent (runs on Laptop)
├── esp/                      # ESP32 Firmware (DHT11 + LED)
├── thingy53/                 # Thingy:53 Firmware (BME680 via Zephyr)
├── raspi/
│   ├── ingestor.py           # Data hub (HTTP Server + BLE Client)
│   ├── sensor_data.db        # SQLite Database (Auto-generated)
│   ├── esp32.conf            # Persistent ESP32 IP (Auto-generated)
│   └── mcp-server/
│       └── app.py            # Starlette-based MCP Server
└── requirements.txt

```

## Setup Instructions

### 1. Raspberry Pi (Central Hub)

**Create Virtual Environment & Install Dependencies:**

```bash
cd project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

**Start the Ingestor:**
This script runs the HTTP server for the ESP32 and the BLE scanner for the Thingy:53.

```bash
python raspi/ingestor.py

```

**Start the MCP Server:**
In a new terminal (with the virtual environment active):

```bash
cd raspi/mcp-server
uvicorn app:app --host 0.0.0.0 --port 4200

```

### 2. Hardware Setup

* **ESP32**: Update `ssid`, `password`, and `pi_url` in `esp/src/main.cpp`. Flash using PlatformIO.
* **Thingy:53**: Flash the Zephyr firmware. It will advertise as `Thingy_Sensor`.

### 3. LLM Agent (Laptop)

The agent requires a local LLM runner (like **Ollama**) to be active.

1. Install [Ollama](https://ollama.com/) and run `ollama run llama3.1`.
2. Update `MCP_URL` in `client/agent_client.py` to your Raspberry Pi's IP.
3. Run the agent:

```bash
python client/agent_client.py

```

## Supported MCP Tools

| Tool Name | Description | Arguments |
| --- | --- | --- |
| `sensors.list` | Returns a list of all active sensor IDs in the DB | None |
| `sensors.latest` | Gets the most recent reading for a sensor | `sensor_id` (e.g., "dht11_temp") |
| `actuators.set` | Controls hardware actuators | `device_id="ESP32"`, `actuator="LED"`, `value="ON"/"OFF"` |
| `system.status` | Checks if the DB, ESP32, and Thingy are online | None |

## API Testing (curl)

**Turn LED ON:**

```bash
curl -X POST http://<RASPI_IP>:4200/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "actuators.set",
      "arguments": {"device_id": "ESP32", "actuator": "LED", "value": "ON"}
    }
  }'

```

## Important Notes

* **Data Persistence**: The ingestor uses a ring buffer that keeps sensor data for only the last 5 minutes.
* **IP Discovery**: The `esp32.conf` file stores the last known IP of the ESP32 so that the MCP server can control the LED even after a restart.