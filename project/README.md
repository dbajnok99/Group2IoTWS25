# Project Structure
```
app/
├── app.py
├── requirements.txt
```

## Setup

### Create Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Start Server
```bash
uvicorn app:app --reload --port 4200
```

## API Examples

### Initialize Connection
```bash
curl -s http://127.0.0.1:4200/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {
        "tools": {},
        "resources": {},
        "prompts": {}
      },
      "clientInfo": {
        "name": "curl-client",
        "version": "0.1"
      }
    }
  }'
```

### List Available Tools
```bash
curl -s http://127.0.0.1:4200/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Call Addition Tool
```bash
curl -s http://127.0.0.1:4200/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"add","arguments":{"a":2,"b":40}}}'
```

## Notes

- Curl commands will later not be performed manually - LLM will do that
- Ollama tool is needed to run all free LLM models (also installs llama server)
- Agent runs on laptop because it's too big / slow otherwise

## Run LLM Agent
```bash
python3.11 agent_client.py
```