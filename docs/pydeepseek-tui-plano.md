# 📋 Plano de Desenvolvimento — `pydeepseek-tui`

> **Stack:** Python 3.11+ · Textual · Pipenv · DeepSeek API (OpenAI-compatible) · PyPI  
> **Estratégia:** Confirme cada etapa antes de gerar. Responda **"ok etapa N"** para iniciar.  
> **Regra:** Um arquivo por vez — aguarde confirmação antes do próximo.

---

## ✅ Etapa 1 — Estrutura do Projeto & Scaffolding

### 1.1 — Arquivos de configuração raiz
- [ ] `Pipfile` — dependências gerenciadas via **pipenv** (prod + dev)
- [ ] `pyproject.toml` — metadados PyPI, entry points, configuração de ferramentas (`ruff`, `black`, `mypy`, `pytest`)
- [ ] `.gitignore` — Python, Pipenv, IDE, `.env`, `dist/`, `__pycache__/`
- [ ] `.python-version` — versão mínima `3.11`
- [ ] `Makefile` — comandos: `make dev`, `make run`, `make test`, `make build`, `make publish`, `make lint`
- [ ] `CHANGELOG.md` — versionamento SemVer inicial `v0.1.0`

### 1.2 — Estrutura de diretórios
```
pydeepseek-tui/
├── Pipfile
├── Pipfile.lock
├── pyproject.toml
├── Makefile
├── .gitignore
├── .python-version
├── CHANGELOG.md
├── README.md
├── src/
│   └── pydeepseek_tui/
│       ├── __init__.py
│       ├── main.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py        # Lê ~/.deepseek-tui/.env
│       │   └── crypto.py          # Criptografia da API key
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── deepseek.py
│       │   ├── openai.py
│       │   ├── ollama.py
│       │   └── anthropic.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── read_file.py
│       │   ├── write_file.py
│       │   ├── shell.py
│       │   ├── list_dir.py
│       │   ├── search_files.py
│       │   ├── git_tool.py
│       │   ├── web_search.py
│       │   └── fetch_url.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── loop.py
│       │   ├── session.py
│       │   └── workspace.py
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── widgets/
│       │   │   ├── chat.py
│       │   │   ├── tool_panel.py
│       │   │   ├── thinking.py
│       │   │   └── statusbar.py
│       │   └── screens/
│       │       ├── main.py
│       │       └── config.py
│       ├── i18n/
│       │   ├── __init__.py
│       │   ├── translator.py
│       │   ├── locales/
│       │   │   ├── pt_BR.json
│       │   │   └── en_US.json
│       └── cli/
│           ├── __init__.py
│           └── commands.py
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_providers.py
    ├── test_tools.py
    ├── test_agent.py
    └── fixtures/
```

---

## ✅ Etapa 2 — Configuração & Criptografia da API Key

### Arquivo de ambiente: `~/.deepseek-tui/.env`
```dotenv
IA_PROVIDER=deepseek
DEEPSEEK_API_KEY_ENCRYPTED=<chave_criptografada>
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
# Futuros providers (basta adicionar aqui):
# OPENAI_API_KEY_ENCRYPTED=<chave_criptografada>
# OPENAI_MODEL=gpt-4o
# GEMINI_API_KEY_ENCRYPTED=<chave_criptografada>
# GEMINI_MODEL=gemini-pro-latest
# ANTHROPIC_API_KEY_ENCRYPTED=<chave_criptografada>
# ANTHROPIC_MODEL=claude-3-5-sonnet
LANGUAGE=pt_BR
```

### Arquivos desta etapa
- [ ] `src/pydeepseek_tui/config/crypto.py` — criptografia com **`cryptography`** (Fernet symmetric encryption); a master key deriva da máquina (`machine-id` + `username`) via PBKDF2
- [ ] `src/pydeepseek_tui/config/settings.py` — lê `~/.deepseek-tui/.env`, descriptografa keys, valida variáveis obrigatórias, expõe `Settings` dataclass
- [ ] `~/.deepseek-tui/.env` — criado automaticamente no primeiro `pydeepseek-tui config`

---

## ✅ Etapa 3 — Camada de Providers (Multi-API)

- [ ] `src/pydeepseek_tui/providers/base.py` — `BaseProvider` abstrato: `chat()`, `stream()`, `list_models()`
- [ ] `src/pydeepseek_tui/providers/deepseek.py` — `DeepSeekProvider` (OpenAI-compatible SDK, modelo via `DEEPSEEK_MODEL`)
- [ ] `src/pydeepseek_tui/providers/openai.py` — `OpenAIProvider`
- [ ] `src/pydeepseek_tui/providers/ollama.py` — `OllamaProvider` (REST local)
- [ ] `src/pydeepseek_tui/providers/anthropic.py` — `AnthropicProvider`
- [ ] `src/pydeepseek_tui/providers/__init__.py` — `ProviderFactory`: instancia o provider correto lendo `IA_PROVIDER` do `.env`

> **Extensibilidade:** Para adicionar um novo provider no futuro, basta:  
> 1. Criar o arquivo `providers/novo_provider.py`  
> 2. Adicionar as variáveis no `.env` (ex: `GEMINI_MODEL=gemini-pro-latest`)  
> 3. Registrar na `ProviderFactory`

---

## ✅ Etapa 4 — Sistema de Tools (Ferramentas do Agente)

- [ ] `src/pydeepseek_tui/tools/base.py` — `BaseTool` abstrato com `name`, `description`, `parameters` (JSON Schema), `execute()`
- [ ] `src/pydeepseek_tui/tools/registry.py` — `ToolRegistry`: registro dinâmico, geração de schema OpenAI function calling
- [ ] `src/pydeepseek_tui/tools/read_file.py` — lê arquivos (offset/limit de linhas)
- [ ] `src/pydeepseek_tui/tools/write_file.py` — cria/edita arquivos (bloqueada em modo `plan`)
- [ ] `src/pydeepseek_tui/tools/shell.py` — executa shell com timeout, captura stdout/stderr
- [ ] `src/pydeepseek_tui/tools/list_dir.py` — lista diretório com filtros glob e profundidade
- [ ] `src/pydeepseek_tui/tools/search_files.py` — busca por regex/texto em arquivos do projeto
- [ ] `src/pydeepseek_tui/tools/git_tool.py` — git: status, diff, add, commit, log, branch
- [ ] `src/pydeepseek_tui/tools/web_search.py` — DuckDuckGo (sem API key) ou SerpAPI (opcional)
- [ ] `src/pydeepseek_tui/tools/fetch_url.py` — download e extração de texto de URLs (`httpx` + `BeautifulSoup`)

---

## ✅ Etapa 5 — Motor do Agente (Agent Loop)

- [ ] `src/pydeepseek_tui/agent/loop.py` — loop: raciocínio → tool call → observação → resposta
  - Parser de `tool_calls` no stream (OpenAI function calling format)
  - Modos de operação:
    - `plan` — somente leitura, tools destrutivas bloqueadas
    - `agent` — executa com confirmação para cada ação
    - `yolo` — executa sem confirmação
- [ ] `src/pydeepseek_tui/agent/session.py` — salvar/restaurar sessões em `~/.deepseek-tui/sessions/` (JSON comprimido)
- [ ] `src/pydeepseek_tui/agent/workspace.py` — snapshot de arquivos antes de edições; undo/rollback

---

## ✅ Etapa 6 — Internacionalização (i18n)

- [ ] `src/pydeepseek_tui/i18n/translator.py` — `Translator`: carrega locale via `LANGUAGE` no `.env`, fallback para `en_US`
- [ ] `src/pydeepseek_tui/i18n/locales/pt_BR.json` — todas as strings da interface em **Português Brasil**
- [ ] `src/pydeepseek_tui/i18n/locales/en_US.json` — todas as strings da interface em **English**

> **Extensibilidade:** Para adicionar um novo idioma, basta criar `locales/es_ES.json` e definir `LANGUAGE=es_ES` no `.env`

---

## ✅ Etapa 7 — Interface TUI com Textual

- [ ] `src/pydeepseek_tui/tui/app.py` — `DeepSeekTUIApp`: app Textual principal, carrega tema, provider e i18n
- [ ] `src/pydeepseek_tui/tui/screens/main.py` — tela principal: sidebar + área de chat + painel de status
- [ ] `src/pydeepseek_tui/tui/screens/config.py` — tela de configuração interativa (API keys, provider, modelo, idioma)
- [ ] `src/pydeepseek_tui/tui/widgets/chat.py` — streaming de markdown em tempo real, syntax highlight de código
- [ ] `src/pydeepseek_tui/tui/widgets/tool_panel.py` — painel de execução de tools (nome, input, output, status)
- [ ] `src/pydeepseek_tui/tui/widgets/thinking.py` — painel colapsável de chain-of-thought (thinking mode)
- [ ] `src/pydeepseek_tui/tui/widgets/statusbar.py` — tokens usados, custo estimado, modo atual, provider/modelo
- [ ] Keybindings: `Ctrl+M` (modo), `Ctrl+P` (provider), `Ctrl+S` (salvar sessão), `Ctrl+Z` (rollback), `?` (ajuda)

---

## ✅ Etapa 8 — CLI Entry Point

- [ ] `src/pydeepseek_tui/cli/commands.py` — comandos via **`click`**:
  - `pydeepseek-tui` — abre a TUI
  - `pydeepseek-tui config` — configuração interativa (salva `.env` com key criptografada)
  - `pydeepseek-tui sessions` — lista/deleta sessões salvas
  - `pydeepseek-tui --provider deepseek --model deepseek-v4-pro --mode agent`
  - `pydeepseek-tui --lang pt_BR`

---

## ✅ Etapa 9 — README.md Completo

- [ ] Seção: **O que é** — descrição do projeto e inspiração no DeepSeek-TUI
- [ ] Seção: **Recursos** — lista completa de funcionalidades
- [ ] Seção: **Bibliotecas utilizadas** — tabela com nome, versão e finalidade
- [ ] Seção: **Instalação** — `pip install pydeepseek-tui` + configuração via `pydeepseek-tui config`
- [ ] Seção: **Configuração** — explicação do `~/.deepseek-tui/.env`, criptografia e multi-provider
- [ ] Seção: **Uso** — exemplos de uso, modos de operação, keybindings
- [ ] Seção: **Internacionalização** — como mudar idioma e como contribuir com traduções
- [ ] Seção: **Agradecimentos** — créditos a Natan Fiuza (`contato@natanfiuza.dev.br`)
- [ ] Seção: **Como contribuir** — guia de contribuição com Pipenv, pull requests e padrões de código

---

## ✅ Etapa 10 — Testes & Qualidade

- [ ] `tests/test_config.py` — testa criptografia/descriptografia, leitura do `.env`
- [ ] `tests/test_providers.py` — testa `ProviderFactory`, mock de chamadas HTTP
- [ ] `tests/test_tools.py` — testa cada tool individualmente com fixtures
- [ ] `tests/test_agent.py` — testa `AgentLoop` com provider mockado
- [ ] Cobertura ≥ 80% via `pytest-cov`
- [ ] Linting: `ruff`, formatação: `black`, tipos: `mypy`
- [ ] CI/CD: GitHub Actions — lint + test em Python 3.11, 3.12, 3.13

---

## ✅ Etapa 11 — Publicação no PyPI

- [ ] Build: `pipenv run python -m build` → gera `wheel` + `sdist`
- [ ] Publicação TestPyPI: `pipenv run twine upload --repository testpypi dist/*`
- [ ] Validação: `pip install --index-url https://test.pypi.org/simple/ pydeepseek-tui`
- [ ] Publicação PyPI: `pipenv run twine upload dist/*`
- [ ] GitHub Actions release: tag `v*` → build → publish automático

---

## 🗺️ Ordem de Execução

```
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
```

## 📦 Dependências Principais (Pipfile)

| Biblioteca | Finalidade |
|---|---|
| `textual` | Interface TUI rica no terminal |
| `openai` | SDK compatível com DeepSeek e OpenAI |
| `anthropic` | Provider Claude |
| `httpx` | Requisições HTTP assíncronas |
| `cryptography` | Criptografia Fernet para API keys |
| `click` | CLI entry points |
| `python-dotenv` | Leitura do `.env` |
| `beautifulsoup4` | Parsing HTML para fetch_url |
| `duckduckgo-search` | Web search sem API key |
| `gitpython` | Operações Git |
| `rich` | Syntax highlight e markdown |
| `pytest` + `pytest-cov` | Testes e cobertura |
| `ruff` + `black` + `mypy` | Lint, formatação e tipos |
| `build` + `twine` | Build e publicação PyPI |

---

> Responda **"ok etapa 1"** para iniciar a geração dos arquivos.  
> Cada arquivo será enviado individualmente aguardando sua confirmação.
