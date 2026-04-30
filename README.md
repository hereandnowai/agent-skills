<div align="center">
  <img src="https://raw.githubusercontent.com/hereandnowai/images/refs/heads/main/logos/logo-of-here-and-now-ai.png" alt="HERE AND NOW AI Logo" width="400"/>

  <h1>Angular 21 Agent Skill — For All AI Coding Agents</h1>

  <p><em>"AI is Good"</em></p>

  <p>
    <img src="https://img.shields.io/badge/Angular-21-DD0031?style=for-the-badge&logo=angular&logoColor=white" alt="Angular 21"/>
    <img src="https://img.shields.io/badge/GitHub_Copilot-Supported-FFDF00?style=for-the-badge&logo=github&logoColor=004040" alt="GitHub Copilot"/>
    <img src="https://img.shields.io/badge/Claude_Code-Supported-FFDF00?style=for-the-badge&logo=anthropic&logoColor=004040" alt="Claude Code"/>
    <img src="https://img.shields.io/badge/Cursor-Supported-FFDF00?style=for-the-badge&logoColor=004040" alt="Cursor"/>
    <img src="https://img.shields.io/badge/Any_AI_Agent-Compatible-004040?style=for-the-badge" alt="Any AI Agent"/>
    <img src="https://img.shields.io/badge/TypeScript-Signals--First-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript"/>
    <img src="https://img.shields.io/badge/Zoneless-by_Default-004040?style=for-the-badge" alt="Zoneless"/>
  </p>
</div>

---

## Overview

This repository contains the **Angular 21 Agent Skill** — a curated, production-grade instruction set compatible with all major AI coding agents. It teaches any AI to generate idiomatic Angular 21 code using the latest framework defaults: **zoneless change detection**, **standalone components**, **signals-first reactivity**, **Signal Forms**, and **Vitest** as the default test runner.

Developed by **[HERE AND NOW AI](https://hereandnowai.com)**, this skill is designed to be **agent-agnostic** — one skill file, works everywhere. Whether you're using GitHub Copilot, Claude Code, Cursor, Antigravity, or any other AI coding assistant, drop this skill in and your agent will produce modern Angular 21 code — not outdated patterns.

---

## Why This Skill?

Angular 21 (released November 2025) marks a complete paradigm shift:

- **Zone.js is gone by default** — reactivity is now entirely signal-based
- **NgModules are obsolete** — all components are standalone
- **Signal Forms replace RxJS-based Reactive Forms** for new projects
- **Vitest** replaces Karma as the default test runner
- **`inject()`** is the only supported DI pattern — no constructor injection

Without this skill, any AI coding agent may fall back to outdated Angular patterns (NgModules, Zone.js, Karma, constructor DI). This skill corrects that — across all agents.

---

## What's Inside

```
agent-skills/
└── angular21/
    └── skills.md     # Core Angular 21 instruction set — works with any AI coding agent
```

### Skill Highlights

| Capability | Coverage |
|---|---|
| Zoneless change detection | `provideZonelessChangeDetection()` |
| Standalone components | Full anatomy with signals |
| Signal Forms (experimental) | `FormField`, `FormGroup`, validators |
| New control flow | `@if`, `@for`, `@switch` |
| `inject()`-based DI | Services, HTTP, Router |
| Vitest testing | Zoneless async patterns |
| `linkedSignal` & `resource` API | Advanced signal patterns |
| Angular ARIA | Accessibility helpers |
| SSR / `afterRenderEffect` | Server-side rendering patterns |

---

## How to Use

This skill file is plain Markdown — load it into whichever AI coding agent you use.

### GitHub Copilot (VS Code)

```json
// .vscode/settings.json
{
  "github.copilot.chat.agent.skills": [
    "./agent-skills/angular21/skills.md"
  ]
}
```

### Claude Code

Reference the skill file in your project's `CLAUDE.md` or pass it as context:

```markdown
<!-- CLAUDE.md -->
@./agent-skills/angular21/skills.md
```

### Cursor

Add the skill to your `.cursor/rules` or reference it in a `.cursorrules` file:

```
# .cursorrules
See ./agent-skills/angular21/skills.md for all Angular 21 coding conventions.
```

### Antigravity & Other Agents

Paste or import `skills.md` as a system prompt / context document in your agent's configuration. The file is self-contained and agent-agnostic.

---

### Trigger Phrases

The skill activates when you use phrases like:

- *"Create an Angular component..."*
- *"Build an Angular 21 app..."*
- *"Write a signal form for..."*
- *"Add a zoneless Angular service..."*
- *"Generate Angular ARIA components..."*

### Example Prompt

```
Build an Angular 21 standalone component for a user profile card with 
signal-based state, a reactive computed display name, and zoneless change detection.
```

---

## Skill Metadata

```yaml
name: angular21
description: >
  Build Angular 21 frontend applications using modern Angular patterns.
  Triggers on: Angular 21, signal forms, zoneless, Angular ARIA, Vitest,
  MCP server, Angular component/service/directive/pipe/route requests.
```

---

## Tech Stack

| Tool | Version / Notes |
|---|---|
| Angular | `^21.0.0` |
| TypeScript | `^5.7` |
| Vitest | Default test runner |
| Signal Forms | `@angular/forms/experimental` |
| Change Detection | Zoneless (no Zone.js) |
| Components | Standalone only |

---

## Compatible AI Coding Agents

| Agent | Integration Method |
|---|---|
| **GitHub Copilot** | `.vscode/settings.json` skill config |
| **Claude Code** | `CLAUDE.md` context reference |
| **Cursor** | `.cursorrules` or `.cursor/rules` |
| **Antigravity** | System prompt / context document |
| **Any MCP-compatible agent** | MCP tool context |
| **Any LLM agent** | Paste as system prompt or context |

---

## Contributing

Contributions to improve the skill's instruction coverage are welcome. Please open a pull request with:

1. The Angular version the instruction targets
2. A before/after example of AI agent output
3. The updated `skills.md` snippet

---

## Connect with Us

<div align="center">

Built with ❤️ by **[HERE AND NOW AI](https://hereandnowai.com)**

| Channel | Link |
|---|---|
| 🌐 Website | [hereandnowai.com](https://hereandnowai.com) |
| 💼 LinkedIn | [linkedin.com/company/hereandnowai](https://www.linkedin.com/company/hereandnowai/) |
| 𝕏 X (Twitter) | [@hereandnow_ai](https://x.com/hereandnow_ai) |
| 📸 Instagram | [@hereandnow_ai](https://instagram.com/hereandnow_ai) |
| ▶️ YouTube | [@hereandnow_ai](https://youtube.com/@hereandnow_ai) |
| 🐙 GitHub | [github.com/hereandnowai](https://github.com/hereandnowai) |
| 📧 Email | [info@hereandnowai.com](mailto:info@hereandnowai.com) |
| 📞 Phone | +91 996 296 1000 |

*"AI is Good"*

</div>
