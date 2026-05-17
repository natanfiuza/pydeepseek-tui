# Análise de Lacunas — pydeepseek-tui

Data: 2026-05-15
Fonte: Comparação entre [Plano Original](../testes/pydeepseek-tui/docs/pydeepseek-tui-plano.md) e estado atual do código

---

## Progresso Geral: ~35% do plano original

| Etapa | Descrição | Completo |
|---|---|---|
| 1 | Scaffolding | 90% |
| 2 | Config & Criptografia | 100% |
| 3 | Multi-provider | 25% |
| 4 | Tools | 40% |
| 5 | Agent Loop | 33% |
| 6 | i18n | 0% |
| 7 | TUI | 15% |
| 8 | CLI | 20% |
| 9 | README | 30% |
| 10 | Testes & Qualidade | 50% |
| 11 | PyPI | 0% |

---

## Lacunas por Etapa

### Etapa 1 — Scaffolding (90%)
- Estrutura real é mais plana que a planeada: `agent.py` vs `agent/` (loop, session, workspace), `app.py` vs `tui/` (app, widgets, screens)
- Faltam: `i18n/`, `tui/widgets/`, `tui/screens/`, `cli/commands.py`, `tests/fixtures/`

### Etapa 2 — Config & Criptografia (100%)
- Corrigido: unificação PBKDF2 + machine-id, variável `DEEPSEEK_API_KEY_ENCRYPTED` consistente

### Etapa 3 — Multi-provider (25%)
- **Feito**: DeepSeekProvider
- **Em falta**: OpenAIProvider, OllamaProvider, AnthropicProvider
- Factory preparada para extensão (comentários no código)

### Etapa 4 — Tools (40%)
- **Feito**: read_file, write_file, web_search, fetch_url, sandbox
- **Em falta**: shell (execução de comandos), list_dir, search_files, git_tool

### Etapa 5 — Agent Loop (33%)
- **Feito**: Loop básico com streaming + function calling, limite de histórico
- **Em falta**: Modos plan/agent/yolo, session save/restore, workspace undo

### Etapa 6 — i18n (0%)
- Nada implementado. Planeado: Translator com JSON locales (pt_BR, en_US)

### Etapa 7 — TUI (15%)
- **Feito**: App básica (Header, Footer, Input, RichLog)
- **Em falta**: Sidebar, chat com syntax highlight, tool_panel, thinking panel, statusbar, tela de config, keybindings avançados

### Etapa 8 — CLI (20%)
- **Feito**: Comando `pydeepseek` (start)
- **Em falta**: `config`, `sessions`, flags `--provider`, `--model`, `--mode`, `--lang`

### Etapa 9 — README (30%)
- README básico existe. Faltam seções de multi-provider, i18n, keybindings, contribuição

### Etapa 10 — Testes (50%)
- 33 testes, cobertura 58% (meta: 80%)
- Sem CI/CD (GitHub Actions)

### Etapa 11 — PyPI (0%)
- Build e publish não configurados

---

## Resumo de Ficheiros em Falta

```
src/pydeepseek_tui/
├── providers/
│   ├── openai.py          # Em falta
│   ├── ollama.py           # Em falta
│   └── anthropic.py        # Em falta
├── tools/
│   ├── shell.py            # Em falta
│   ├── list_dir.py         # Em falta
│   ├── search_files.py     # Em falta
│   └── git_tool.py         # Em falta
├── agent/
│   ├── __init__.py         # Em falta (mover agent.py para cá)
│   ├── loop.py             # Em falta
│   ├── session.py          # Em falta
│   └── workspace.py        # Em falta
├── tui/
│   ├── __init__.py         # Em falta
│   ├── screens/
│   │   ├── __init__.py     # Em falta
│   │   ├── main.py         # Em falta
│   │   └── config.py       # Em falta
│   └── widgets/
│       ├── __init__.py     # Em falta
│       ├── chat.py         # Em falta
│       ├── tool_panel.py   # Em falta
│       ├── thinking.py     # Em falta
│       └── statusbar.py    # Em falta
├── i18n/
│   ├── __init__.py         # Em falta
│   ├── translator.py       # Em falta
│   └── locales/
│       ├── pt_BR.json      # Em falta
│       └── en_US.json      # Em falta
└── cli/
    ├── __init__.py         # Em falta
    └── commands.py         # Em falta
```
