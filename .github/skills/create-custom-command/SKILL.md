---
name: create-custom-command
description: Creates custom commands for VS Code GitHub Copilot Chat as .prompt.md files
---

# Custom Command Creation for VS Code GitHub Copilot

Custom commands (prompt files) are Markdown files that create reusable slash commands in VS Code Copilot Chat.

## File Structure

Prompt files use `.prompt.md` extension with this structure:

```markdown
---
description: 'Short description of what this command does'
name: 'command-name'
argument-hint: 'Optional hint text shown in chat input'
agent: 'ask|edit|agent|custom-agent-name'
model: 'GPT-4o|Claude Sonnet 4'
tools: ['tool1', 'tool2']
---

Prompt body content goes here.
Instructions for the AI to follow.

Reference files with Markdown links: [file.md](../path/to/file.md)
Reference tools with: #tool:toolName

Variables available:
- ${workspaceFolder} - workspace root path
- ${file} - current file path
- ${selectedText} - selected text in editor
- ${input:variableName} - user input variable
- ${input:variableName:placeholder} - with placeholder text
```

## Locations

**Workspace prompts** (team-shared):

- Location: `.github/prompts/` in repository root
- Available only in that workspace
- Committed to version control

**User prompts** (personal):

- Location: VS Code profile directory
- Available across all workspaces
- Can sync via Settings Sync

## Creating a Prompt File

1. In Chat view, select **Configure Chat** (gear) > **Prompt Files** > **New prompt file**
2. Choose location (Workspace or User profile)
3. Enter filename (becomes command name)
4. Add YAML frontmatter and prompt body

## Usage

Type `/command-name` in Copilot Chat to run the prompt.

## Example

File: `.github/prompts/load-instructions.prompt.md`

```markdown
---
description: 'Loads private instructions into chat context'
name: 'load-instructions'
---

Load the file C:\.github\copilot-chat\instructions.md using the view tool and apply its content to all responses in this chat session.
```

After creating, use `/load-instructions` in VS Code Copilot Chat.
