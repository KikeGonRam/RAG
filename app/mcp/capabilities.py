def get_mcp_capabilities() -> dict:
    """MCP-style tool manifest for integration gateways/agents."""
    return {
        "name": "rag-ollama-mcp",
        "version": "1.0.0",
        "transport": ["http"],
        "tools": [
            {
                "name": "ask_question",
                "description": "Ask the RAG assistant in a collaborator session.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "collection": {"type": "string"},
                        "session_id": {"type": "integer"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["question"],
                },
                "http": {"method": "POST", "path": "/ask"},
            },
            {
                "name": "list_chats",
                "description": "List collaborator chat sessions.",
                "input_schema": {"type": "object", "properties": {}},
                "http": {"method": "GET", "path": "/chats"},
            },
            {
                "name": "create_chat",
                "description": "Create a collaborator chat session.",
                "input_schema": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                },
                "http": {"method": "POST", "path": "/chats"},
            },
            {
                "name": "admin_create_key",
                "description": "Create collaborator API key from admin panel backend.",
                "input_schema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
                "http": {"method": "POST", "path": "/admin/keys"},
            },
        ],
    }
