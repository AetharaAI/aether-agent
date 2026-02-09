## User Profile & Tool System Fixes - Implementation Complete

I've implemented all the fixes you requested:

### 1. Full User Profile Parsing from AETHER_USER.md
**New parser function:** `_parse_user_profile_from_markdown()` in `api_server.py`

Now extracts ALL details:
- **Name:** CJ
- **Title:** Founder, Owner, CEO, CTO — AetherPro Technologies
- **Pronouns:** he/him
- **Location:** Greensburg, Indiana
- **Timezone:** America/Indianapolis
- **Background:** Master Electrician, Licensed Electrical Contractor, Artificial & Digital Intelligence Systems Architect & Engineer
- **Projects:** Passport IAM, Triad Intelligence, CMC, Aether Desktop
- **Working Style:** What CJ appreciates (solutions that "just work", infrastructure that runs itself, etc.)

The bootstrap function now logs:
```
→ User profile bootstrapped from AETHER_USER.md
  Name: CJ
  Title: Founder, Owner, CEO, CTO — AetherPro Technologies
  Background: Master Electrician, Licensed Electrical Contractor...
```

### 2. Updated System Prompt Builder
**Modified:** `build_system_prompt()` in `aether_memory.py`

Now includes full user profile sections:
```
USER PROFILE:
- Name: CJ
- Title: Founder, Owner, CEO, CTO — AetherPro Technologies
- Pronouns: he/him
- Location: Greensburg, Indiana
- Timezone: America/Indianapolis

BACKGROUND & CREDENTIALS:
- Master Electrician
- Licensed Electrical Contractor
- Artificial & Digital Intelligence Systems Architect & Engineer

ACTIVE PROJECTS:
- Passport IAM
- Triad Intelligence
...
```

### 3. New File Tools Added
**Updated:** `aether/tools/core_tools.py` and `aether/tools/__init__.py`

Three new tools:
- **`file_read`** - Read file contents with line limits/offsets
- **`file_list`** - List directory contents (recursive option)
- **`file_write`** - Write/create files (AUTO permission - requires confirmation)

### 4. Tool Discovery System
**New endpoints in `api_server.py`:**
- `GET /api/tools` - List all available tools
- `GET /api/tools/{tool_name}` - Get specific tool details
- `POST /api/tools/execute/{tool_name}` - Execute a tool via API

**New functions in `aether/tools/__init__.py`:**
- `get_available_tools()` - Get tool metadata
- `get_tool_schemas()` - Get tool schemas for LLM
- `format_tools_for_prompt()` - Format tools for system prompt

### 5. Tools Now in System Prompt
The system prompt now includes:
```
=== AVAILABLE TOOLS ===

file_read:
  Description: Read the contents of a file from the filesystem
  Permission: semi
  Parameters:
    - path: Absolute or relative path to the file (required)
    - limit: Maximum number of lines to read
    - offset: Line offset to start reading from

file_list:
  Description: List files and directories at a given path
  ...

=== TOOL USAGE ===
To use a tool, you must:
1. Check if you have permission (check tool.permission)
2. Call the tool with required parameters
3. Wait for the result before proceeding
4. NEVER hallucinate tool results - only report actual tool outputs

If you don't have a tool for a task, say so explicitly.
```

### Key Behavioral Changes

1. **No more hallucination:** Aether now knows exactly which tools it has
2. **Full user context:** Will know you're a Master Electrician, CEO, CTO, etc.
3. **Tool awareness:** Can query `/api/tools` to discover capabilities
4. **Permission checking:** Won't claim to use tools in restricted modes

### To Test

Restart the Docker containers and ask Aether:
1. "What's my full title and background?" (should include CEO, CTO, Master Electrician)
2. "What tools do you have available?" (should list 8 tools including file_read, file_list)
3. "Use the file_list tool to show me the workspace directory" (should actually work now)
