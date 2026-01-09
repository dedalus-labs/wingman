# Wingman

<div align="center">
  <code>uv tool install wingman-cli</code>
</div>
<br>

<div align="center">
  <img src="assets/readme.png" alt="Ralph 'Wingman' Wiggum flying with Dedalus wings" width="720">
</div>

<div align="center">
  <em>AI-powered TUI coding assistant for the terminal. Your copilot for code.</em>
</div>

## Features

- **Multi-model support**: OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek
- **Coding tools**: File read/write, shell commands, grep, with diff previews
- **MCP integration**: Connect to Model Context Protocol servers
- **Split panels**: Work on multiple conversations simultaneously
- **Checkpoints**: Automatic file snapshots with rollback support
- **Project memory**: Persistent context per directory
- **Image support**: Attach and analyze images in conversations
- **Context management**: Auto-compaction when context runs low

## Installation

### Using uv (recommended)

```bash
uv tool install wingman-cli
```

<details>
  <summary><span style="color: #7a7a7a; font-style: italic;">Installing <code>uv</code></span></summary>

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip/pipx
pip install uv
```

</details>

### Using pip

```bash
pip install wingman-cli
```

### Using pipx

```bash
pipx install wingman-cli
```

## Quick Start

1. **Run Wingman**:

   ```bash
   wingman
   ```

2. **Enter your Dedalus API key** when prompted

   - Get your key at [dedaluslabs.ai/dashboard/api-keys](https://dedaluslabs.ai/dashboard/api-keys)

3. **Start chatting** - Type your message and press Enter

## Commands

| Command          | Description        |
| ---------------- | ------------------ |
| `/new`           | Start new chat     |
| `/rename <name>` | Rename session     |
| `/delete`        | Delete session     |
| `/split`         | Split panel        |
| `/close`         | Close panel        |
| `/model`         | Switch model       |
| `/code`          | Toggle coding mode |
| `/cd <path>`     | Change directory   |
| `/ls`            | List files         |
| `/ps`            | List processes     |
| `/kill <id>`     | Stop process       |
| `/history`       | View checkpoints   |
| `/rollback <id>` | Restore checkpoint |
| `/diff`          | Show changes       |
| `/compact`       | Compact context    |
| `/context`       | Context usage      |
| `/mcp`           | MCP servers        |
| `/memory`        | Project memory     |
| `/export`        | Export session     |
| `/import <file>` | Import file        |
| `/key`           | API key            |
| `/clear`         | Clear chat         |
| `/help`          | Show help          |

## Configuration

Wingman stores configuration in `~/.wingman/`:

```
~/.wingman/
├── config.json      # API key and settings
├── sessions/        # Chat history
├── checkpoints/     # File snapshots
└── memory/          # Project memory files
```

## Supported Models

- **OpenAI**: GPT-4.1, GPT-4o, o1, o3, o4-mini
- **Anthropic**: Claude Opus 4.5, Sonnet 4.5, Haiku 4.5, Sonnet 4
- **Google**: Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash
- **xAI**: Grok 4, Grok 3
- **DeepSeek**: DeepSeek Chat, DeepSeek Reasoner
- **Mistral**: Mistral Large, Mistral Small, Codestral

## Requirements

- Python 3.10+
- A [Dedalus API key](https://dedaluslabs.ai/dashboard/api-keys)

### Optional: Faster Search (Recommended)

Install [fd](https://github.com/sharkdp/fd) and [ripgrep](https://github.com/BurntSushi/ripgrep) for significantly faster file operations:

```bash
# macOS
brew install fd ripgrep

# Ubuntu/Debian
sudo apt install fd-find ripgrep

# Arch
sudo pacman -S fd ripgrep
```

Wingman automatically detects and uses these tools when available, falling back to `find`/`grep` otherwise.

## License

MIT. See [LICENSE](LICENSE) for details.

## Links

- [Dedalus Labs](https://dedaluslabs.ai)
- [Documentation](https://docs.dedaluslabs.ai)
- [Discord](https://discord.com/invite/RuDhZKnq5R)

---

<div align="center">
  <sub>Dedalus Labs © 2026.</sub>
</div>

---
