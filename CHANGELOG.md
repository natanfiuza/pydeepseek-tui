# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

### Planejado
- Suporte a múltiplos providers de IA (OpenAI, Anthropic, Ollama)
- Modo RLM fan-out: sub-agentes paralelos para análise
- Exportação de sessões em Markdown
- Plugin system para tools customizadas
- Suporte a `es_ES` (Espanhol) e `fr_FR` (Francês)

---

## [0.1.0] — 2026-05-13

### Adicionado
- Estrutura inicial do projeto com `src` layout
- Gerenciamento de dependências via **Pipenv**
- Configuração de qualidade: `ruff`, `black`, `mypy`
- Suite de testes com `pytest` + `pytest-cov` (cobertura mínima 80%)
- `Makefile` com comandos de desenvolvimento, testes, build e publicação
- Camada de providers com interface abstrata `BaseProvider`
  - `DeepSeekProvider` — provider padrão (`deepseek-v4-pro`)
  - `OpenAIProvider`, `OllamaProvider`, `AnthropicProvider` (estrutura base)
- Sistema de ferramentas (tools) do agente:
  - `read_file` — leitura de arquivos com offset/limit
  - `write_file` — criação e edição de arquivos
  - `shell` — execução de comandos shell com timeout
  - `list_dir` — listagem de diretórios com filtros glob
  - `search_files` — busca por regex em arquivos do projeto
  - `git_tool` — operações Git (status, diff, add, commit, log)
  - `web_search` — busca web via DuckDuckGo (sem API key)
  - `fetch_url` — download e extração de texto de URLs
- Motor do agente (`AgentLoop`) com 3 modos de operação:
  - `plan` — somente leitura
  - `agent` — executa com confirmação
  - `yolo` — executa sem confirmação
- Gerenciamento de sessões: salvar e restaurar em `~/.deepseek-tui/sessions/`
- Workspace rollback: snapshot de arquivos antes de edições
- Interface TUI com **Textual**:
  - Layout: sidebar + área de chat + painel de status
  - Streaming de markdown em tempo real com syntax highlight
  - Painel de execução de tools com indicadores de status
  - Painel colapsável de thinking mode (chain-of-thought)
  - Barra de status com tokens usados e custo estimado
  - Suporte a temas dark/light
- CLI via **Click**:
  - `pydeepseek-tui` — abre a TUI
  - `pydeepseek-tui config` — configuração interativa com criptografia de API key
  - `pydeepseek-tui sessions` — gerenciamento de sessões
- **Internacionalização (i18n)**:
  - Português Brasil (`pt_BR`) — idioma padrão
  - Inglês (`en_US`)
- **Criptografia** de API keys com `cryptography` (Fernet + PBKDF2)
  - Chaves armazenadas em `~/.deepseek-tui/.env` de forma segura
- Variáveis de ambiente padronizadas:
  - `IA_PROVIDER` — provider ativo
  - `DEEPSEEK_MODEL` — modelo DeepSeek
  - `LANGUAGE` — idioma da interface
- CI/CD com GitHub Actions:
  - Lint + testes em Python 3.11, 3.12, 3.13
  - Publicação automática no PyPI via tag `v*`
- `README.md` completo com instalação, uso, configuração e guia de contribuição

### Segurança
- API keys nunca armazenadas em texto plano
- Master key derivada de `machine-id + username` via PBKDF2 (sem senha adicional)
- `.env` fora do diretório do projeto (`~/.deepseek-tui/`)

---

## Convenções de versionamento

```
MAJOR.MINOR.PATCH

MAJOR — mudanças incompatíveis com versões anteriores
MINOR — novas funcionalidades compatíveis com versões anteriores
PATCH — correções de bugs compatíveis com versões anteriores
```

### Tipos de mudança

| Tipo | Descrição |
|---|---|
| `Adicionado` | Novas funcionalidades |
| `Modificado` | Mudanças em funcionalidades existentes |
| `Descontinuado` | Funcionalidades que serão removidas em breve |
| `Removido` | Funcionalidades removidas |
| `Corrigido` | Correções de bugs |
| `Segurança` | Correções de vulnerabilidades |

---

[Não lançado]: https://github.com/natanfiuza/pydeepseek-tui/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/natanfiuza/pydeepseek-tui/releases/tag/v0.1.0
