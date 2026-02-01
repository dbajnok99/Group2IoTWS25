import json
import httpx
from openai import OpenAI


# il tuo Starlette MCP - your starlette MCP
MCP_URL = "http://127.0.0.1:4200/mcp/"

# SCEGLI UNO: - Choose one:
# OLLAMA_BASE_URL = "http://localhost:11434/v1" # Ollama OpenAI-compat
# LMSTUDIO_BASE_URL = "http://localhost:1234/v1" # LM Studio OpenAI-compat

# <-- cambia a LM Studio se vuoi - check out LM Studio if you want
BASE_URL = "http://localhost:11434/v1"
MODEL = "llama3.1"  # <-- metti il model id che hai caricato - enter the model you chose


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

    # result.content è una lista di content items (es. TextContent)
    # result.content is a list of content items

    content = res["result"]["content"]

    texts = []

    for c in content:
        if c.get("type") == "text":
            texts.append(c.get("text", ""))

    return "\n".join(texts).strip()


def main():
    # 1) MCP handshake + tools discovery
    mcp_initialize()

    mcp_tools = mcp_list_tools()

    openai_tools = mcp_tools_to_openai_tools(mcp_tools)

    # 2) Connect to local LLM via OpenAI-compatible API
    client = OpenAI(
        base_url=BASE_URL,
        api_key="not-needed",  # LM Studio spesso non richiede key; Ollama accetta qualsiasi stringa - LM Studio often doesn't require a key; Ollama accepts any string
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Always use tools!"},
    ]

    print("Agent Client is ready. Type 'exit' or 'quit' to end the conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        messages.append({"role": "user", "content": user_input})

        # 3) First completion (model may ask for tool)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.2,
        )

        msg = resp.choices[0].message

        # If the model requested a tool call:
        if getattr(msg, "tool_calls", None):
            print("Agent: Using tool...")
            for tc in msg.tool_calls:
                fn = tc.function.name

            args = json.loads(tc.function.arguments or "{}")

            tool_output = mcp_call_tool(fn, args)

            # Append tool result in OpenAI format
            messages.append(msg)  # assistant tool call message

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output,
                }
            )

            # 4) Second completion with tool outputs
            resp2 = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.2,
            )

            agent_response = resp2.choices[0].message.content
            print(f"Agent: {agent_response}")
            messages.append({"role": "assistant", "content": agent_response})

        else:
            # Model answered directly
            print("Agent: Answering directly (no tool used)...")
            agent_response = msg.content
            print(f"Agent: {agent_response}")
            messages.append({"role": "assistant", "content": agent_response})


if __name__ == "__main__":

    main()
