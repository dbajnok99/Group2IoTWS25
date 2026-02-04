import json
import httpx
from openai import OpenAI


# starlette MCP
MCP_URL = "http://192.168.0.150:4200/mcp/"
BASE_URL = "http://localhost:11434/v1"
MODEL = "llama3.1"


def mcp_call(payload: dict) -> dict:
    """Call MCP endpoint (JSON-RPC)."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        r = client.post(MCP_URL, headers=headers, json=payload)

    r.raise_for_status()

    return r.json()


def mcp_initialize() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "local-agent", "version": "0.1"},
        },
    }

    _ = mcp_call(payload)


def mcp_list_tools() -> list[dict]:
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    res = mcp_call(payload)

    return res["result"]["tools"]


def mcp_tools_to_openai_tools(mcp_tools: list[dict]) -> list[dict]:
    """

    Convert MCP tool schema -> OpenAI tool schema (function calling).

    MCP returns tools with inputSchema (JSON schema).

    """

    out = []

    for t in mcp_tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            }
        )

    return out


def mcp_call_tool(name: str, args: dict) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }

    res = mcp_call(payload)

    # result.content is a list of content items

    content = res["result"]["content"]

    texts = []

    for c in content:
        if c.get("type") == "text":
            texts.append(c.get("text", ""))

    return "\n".join(texts).strip()


def process_message(user_input, client, openai_tools, available_tool_names, system_message):
    messages = [
        system_message,
        {"role": "user", "content": user_input}
    ]

    while True:
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.2,
            )
        except httpx.ConnectError as e:
            print(f"Agent: I couldn't connect to the model at {BASE_URL}. Please make sure the server is running.")
            return

        msg = resp.choices[0].message
        messages.append(msg)

        if getattr(msg, "tool_calls", None):
            print("Agent: Using tool(s)...")
            all_tools_available = True
            for tc in msg.tool_calls:
                fn = tc.function.name
                if fn not in available_tool_names:
                    print(f"Agent: I don't have the capability to use the '{fn}' tool.")
                    all_tools_available = False
                    break
            
            if not all_tools_available:
                break

            for tc in msg.tool_calls:
                fn = tc.function.name
                args = json.loads(tc.function.arguments or "{}")

                print(f"  - Calling tool: {fn} with arguments: {args}")
                tool_output = mcp_call_tool(fn, args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_output,
                    }
                )
        else:
            print(f"Agent: {msg.content}")
            break


def main():
    # 1) MCP handshake + tools discovery
    mcp_initialize()

    mcp_tools = mcp_list_tools()
    available_tool_names = {tool['name'] for tool in mcp_tools}
    openai_tools = mcp_tools_to_openai_tools(mcp_tools)

    # 2) Connect to local LLM via OpenAI-compatible API
    client = OpenAI(
        base_url=BASE_URL,
        api_key="not-needed",
    )

    system_message = {"role": "system", "content": """You are a helpful assistant. 
    AVAILABLE DEVICES:
    - ESP32: Has an actuator 'LED' (boolean) and a sensor 'dht11_temp'.
    - Thingy: Has sensors 'Temperature' and 'Humidity'.
    You MUST use MCP tools. Never invent values."""}
    print("Agent Client is ready. Type 'exit' or 'quit' to end the conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        process_message(user_input, client, openai_tools, available_tool_names, system_message)


if __name__ == "__main__":

    main()
