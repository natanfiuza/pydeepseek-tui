# Plano Completo de Implementação — pydeepseek-tui

## Contexto

O projeto está a ~35% do plano original de 11 etapas. Após correções críticas (criptografia, sandbox, testes), o núcleo está estável. Este plano cobre todas as lacunas restantes organizadas em 8 sprints por ordem de valor entregue.

---

## Sprint 1 — Novas Tools (shell, list_dir, search_files, git)

**Objetivo**: Completar o conjunto de 8 tools do plano original.

### 1.1 — ShellTool (`tools/shell.py`)
- Usa `asyncio.create_subprocess_shell` com timeout configurável
- Parâmetros: `command` (string), `timeout` (int, default 30s), `cwd` (string, opcional)
- Captura stdout e stderr separadamente
- Retorna: exit code + stdout + stderr truncado a 8000 chars
- Sandbox: só executa se o cwd estiver na allowlist
- A ferramenta deve descrever claramente os riscos no `description` para a IA

### 1.2 — ListDirTool (`tools/list_dir.py`)
- Parâmetros: `path` (string), `pattern` (glob, default `*`), `max_depth` (int, default 2)
- Usa `pathlib.Path.glob` com `**` para profundidade
- Retorna lista formatada com tipo (F/D), tamanho, nome
- Sandbox: valida path com `is_path_allowed`

### 1.3 — SearchFilesTool (`tools/search_files.py`)
- Parâmetros: `pattern` (regex), `path` (dir), `file_pattern` (glob, default `*`), `max_results` (int, default 20)
- Usa `re.search` linha a linha em ficheiros de texto
- Ignora binários (tenta decode UTF-8, skip se falhar)
- Sandbox: valida path
- Retorna: ficheiro:linha: conteúdo com contexto

### 1.4 — GitTool (`tools/git_tool.py`)
- Parâmetros: `action` (enum: status/diff/log/branch/add/commit), `path` (repo), `message` (para commit)
- Usa `subprocess.run` com `git` CLI (mais fiável que GitPython)
- Ações disponíveis: `status`, `diff` (unstaged + staged), `log` (últimos 10), `branch` (list), `add` (specific files), `commit`
- Sandbox: valida path
- `add` e `commit` requerem `overwrite=true` (confirmação explícita)

### Ficheiros
- `src/pydeepseek_tui/tools/shell.py` — novo
- `src/pydeepseek_tui/tools/list_dir.py` — novo
- `src/pydeepseek_tui/tools/search_files.py` — novo
- `src/pydeepseek_tui/tools/git_tool.py` — novo
- `src/pydeepseek_tui/tools/registry.py` — atualizar `get_core_registry()`

---

## Sprint 2 — Multi-Provider (OpenAI + Anthropic)

**Objetivo**: Suportar múltiplos providers de IA, completando a visão do `ProviderFactory`.

### 2.1 — OpenAIProvider (`providers/openai.py`)
- Reusa `openai.AsyncOpenAI` com `base_url` padrão da OpenAI
- Lê `OPENAI_API_KEY` e `OPENAI_MODEL` das variáveis de ambiente
- Métodos: `ask()`, `stream()` (implementação quase idêntica à do DeepSeek)
- Opcional: `close()`

### 2.2 — AnthropicProvider (`providers/anthropic.py`)
- Usa SDK `anthropic.AsyncAnthropic`
- Lê `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL` das variáveis de ambiente
- Adapta messages do formato OpenAI para Anthropic:
  - System message extraída do array e passada como parâmetro separado
  - Tool calls convertidas para o formato Anthropic (content blocks)
  - Streaming adaptado para retornar delta compatível com o Agent
- Requer re-adição de `anthropic` ao PipFile

### 2.3 — Atualizar Factory
- `ProviderFactory.get_provider("openai")` → `OpenAIProvider()`
- `ProviderFactory.get_provider("anthropic")` → `AnthropicProvider()`
- `ProviderFactory.get_provider("deepseek")` → já existe

### 2.4 — Atualizar Settings
- Adicionar campos: `openai_api_key`, `openai_model`, `anthropic_api_key`, `anthropic_model`
- Ler de `os.environ` respectivos

### 2.5 — Atualizar CLI
- `ensure_api_key()` genérico que verifica a chave do provider ativo
- Suporte a onboarding para OpenAI e Anthropic

### Ficheiros
- `src/pydeepseek_tui/providers/openai.py` — novo
- `src/pydeepseek_tui/providers/anthropic.py` — novo
- `src/pydeepseek_tui/providers/factory.py` — atualizar
- `src/pydeepseek_tui/config/settings.py` — adicionar campos
- `src/pydeepseek_tui/cli.py` — generalizar onboarding
- `PipFile` — re-adicionar `anthropic`

---

## Sprint 3 — Modos de Operação do Agente

**Objetivo**: Implementar os modos plan/agent/yolo que controlam o nível de autonomia.

### 3.1 — Refactor: `agent.py` → `agent/` package
- `agent/__init__.py` — re-exporta `Agent`
- `agent/loop.py` — lógica do loop (extraída de `agent.py`)
- `agent/session.py` — save/restore (Sprint 7)
- `agent/workspace.py` — undo/rollback (Sprint 7)
- O `Agent` atual mantém-se, mas o loop é movido para `loop.py`

### 3.2 — Enum `AgentMode`
- `plan` — só tools de leitura (read_file, list_dir, search_files, web_search, fetch_url, git status/diff/log)
- `agent` — todas as tools, mas pede confirmação para destrutivas (write_file com overwrite, shell, git add/commit)
- `yolo` — todas as tools sem confirmação

### 3.3 — Implementação
- `BaseTool` ganha propriedade `is_destructive: bool` (default False)
- `WriteFileTool`, `ShellTool`, `GitTool` (add/commit) marcam `is_destructive = True`
- `Agent.__init__` recebe `mode: AgentMode = AgentMode.AGENT`
- No loop, antes de executar tool destrutiva:
  - `plan`: bloqueia com erro
  - `agent`: pede confirmação (yield pergunta, espera input — precisa de callback ou integração TUI)
  - `yolo`: executa sem perguntar
- A confirmação no modo `agent` será feita via callback injetável (`on_confirm`) para a TUI tratar

### Ficheiros
- `src/pydeepseek_tui/agent/__init__.py` — novo
- `src/pydeepseek_tui/agent/loop.py` — novo (extraído de agent.py)
- `src/pydeepseek_tui/agent/session.py` — stub
- `src/pydeepseek_tui/agent/workspace.py` — stub
- `src/pydeepseek_tui/agent.py` — simplificar para re-exportar
- `src/pydeepseek_tui/tools/base.py` — adicionar `is_destructive`
- `src/pydeepseek_tui/tools/write_file.py` — marcar `is_destructive = True`
- `src/pydeepseek_tui/app.py` — integrar callback de confirmação

---

## Sprint 4 — Internacionalização (i18n)

**Objetivo**: Suportar Português e Inglês com sistema extensível.

### 4.1 — Translator (`i18n/translator.py`)
- Classe `Translator` com singleton
- Carrega JSON do locale definido em `LANGUAGE` (`.env`)
- Fallback: se chave não existe no locale atual, tenta `en_US`, depois retorna a própria chave
- Método: `t(key: str, **kwargs) -> str` com suporte a `{var}` substitution

### 4.2 — Locale files
- `pt_BR.json` — ~50 strings: títulos, labels, mensagens de erro, tooltips
- `en_US.json` — mesmas chaves em inglês
- Estrutura: flat JSON com chaves semânticas (`"app.title"`, `"error.api_key_missing"`, etc.)

### 4.3 — Integração
- Substituir strings hardcoded no `app.py`, `cli.py`, tools, agent por chamadas `t()`
- O Translator é inicializado no arranque com o locale das settings

### Ficheiros
- `src/pydeepseek_tui/i18n/__init__.py` — novo
- `src/pydeepseek_tui/i18n/translator.py` — novo
- `src/pydeepseek_tui/i18n/locales/pt_BR.json` — novo
- `src/pydeepseek_tui/i18n/locales/en_US.json` — novo

---

## Sprint 5 — TUI Avançada

**Objetivo**: Interface rica com sidebar, syntax highlight, e painéis informativos.

### 5.1 — Refactor: `app.py` → `tui/` package
- `tui/app.py` — `PyDeepSeekApp` (movido de `app.py`)
- `tui/screens/main.py` — layout principal com grid
- `tui/screens/config.py` — ecrã de configuração interativa
- `tui/widgets/chat.py` — widget de chat com streaming Markdown e syntax highlight via Rich
- `tui/widgets/tool_panel.py` — painel que mostra tool calls em execução (nome, input, output)
- `tui/widgets/thinking.py` — painel colapsável para chain-of-thought
- `tui/widgets/statusbar.py` — barra de status: tokens, custo estimado, modo, provider

### 5.2 — Layout Principal
```
+---------------------------+-----------------------+
| Sidebar                   | Chat Area             |
| - Modo (plan/agent/yolo) | - Mensagens           |
| - Provider/Modelo         | - Streaming           |
| - Sessões                 | - Tool results inline |
|                           |                       |
+---------------------------+-----------------------+
| Status Bar: tokens • custo • modo • provider      |
+---------------------------------------------------+
```

### 5.3 — Keybindings
- `Ctrl+M` — ciclo de modos (plan → agent → yolo)
- `Ctrl+P` — ciclo de providers (deepseek → openai → anthropic)
- `Ctrl+S` — salvar sessão
- `Ctrl+Z` — undo (rollback de ficheiro)
- `?` — ajuda com lista de atalhos

### Ficheiros
- `src/pydeepseek_tui/tui/__init__.py` — novo
- `src/pydeepseek_tui/tui/app.py` — movido de app.py
- `src/pydeepseek_tui/tui/screens/__init__.py` — novo
- `src/pydeepseek_tui/tui/screens/main.py` — novo
- `src/pydeepseek_tui/tui/screens/config.py` — novo
- `src/pydeepseek_tui/tui/widgets/__init__.py` — novo
- `src/pydeepseek_tui/tui/widgets/chat.py` — novo
- `src/pydeepseek_tui/tui/widgets/tool_panel.py` — novo
- `src/pydeepseek_tui/tui/widgets/thinking.py` — novo
- `src/pydeepseek_tui/tui/widgets/statusbar.py` — novo
- `src/pydeepseek_tui/app.py` — simplificar para re-exportar

---

## Sprint 6 — CLI Completo

**Objetivo**: Comandos CLI para config, sessões e flags de arranque.

### 6.1 — Refactor: `cli.py` → `cli/` package
- `cli/commands.py` — todos os comandos Click

### 6.2 — Comandos
- `pydeepseek` — abre TUI (existente)
- `pydeepseek config` — assistente interativo de configuração
  - Selecionar provider padrão
  - Inserir/alterar API keys (encriptadas)
  - Selecionar modelo
  - Selecionar idioma
- `pydeepseek sessions` — lista sessões salvas
- `pydeepseek sessions <id>` — carrega sessão específica
- `pydeepseek sessions --delete <id>` — apaga sessão

### 6.3 — Flags
- `--provider deepseek|openai|anthropic` — sobrescreve provider do .env
- `--model <model_id>` — sobrescreve modelo
- `--mode plan|agent|yolo` — define modo inicial
- `--lang pt_BR|en_US` — sobrescreve idioma

### Ficheiros
- `src/pydeepseek_tui/cli/__init__.py` — novo
- `src/pydeepseek_tui/cli/commands.py` — novo (extraído de cli.py + novos comandos)
- `src/pydeepseek_tui/cli.py` — simplificar para re-exportar

---

## Sprint 7 — Sessões e Workspace

**Objetivo**: Persistência de conversas e capacidade de desfazer alterações.

### 7.1 — Session (`agent/session.py`)
- `Session` dataclass: id, timestamp, provider, model, mode, conversation_history, metadata
- `save(session)` — serializa para JSON em `~/.deepseek-tui/sessions/{id}.json`
- `load(session_id)` — desserializa e reconstrói Agent
- `list_sessions()` — lista sessões com metadata (data, primeiras 100 chars da conversa)
- `delete(session_id)` — remove ficheiro
- Compressão opcional com `gzip`

### 7.2 — Workspace (`agent/workspace.py`)
- `FileSnapshot` — guarda path + hash SHA-256 + cópia do conteúdo antes de edição
- `snapshot(file_path)` — cria snapshot antes de write_file
- `undo(file_path)` — restaura versão anterior
- `undo_all()` — restaura todos os ficheiros alterados na sessão atual
- Snapshots guardados em `~/.deepseek-tui/workspace/{session_id}/`

### Ficheiros
- `src/pydeepseek_tui/agent/session.py` — implementar (criado como stub no Sprint 3)
- `src/pydeepseek_tui/agent/workspace.py` — implementar (criado como stub no Sprint 3)

---

## Sprint 8 — Testes, CI/CD, PyPI

**Objetivo**: Atingir 80%+ cobertura, CI funcional, publicação.

### 8.1 — Testes
- `tests/test_shell.py` — mock de subprocess
- `tests/test_list_dir.py` — com tmp_path
- `tests/test_search_files.py` — com tmp_path
- `tests/test_git_tool.py` — com repo git temporário
- `tests/test_openai_provider.py` — mock de AsyncOpenAI
- `tests/test_anthropic_provider.py` — mock de AsyncAnthropic
- `tests/test_agent_modes.py` — plan bloqueia, agent confirma, yolo executa
- `tests/test_translator.py` — load, fallback, substitution
- `tests/test_session.py` — save/load roundtrip
- `tests/test_workspace.py` — snapshot/undo

### 8.2 — CI/CD
- `.github/workflows/ci.yml`:
  - Matrix: Python 3.11, 3.12, 3.13
  - Passos: checkout, setup python, pipenv install --dev, ruff check, black --check, mypy src, pytest --cov
  - Cobertura mínima: 80%

### 8.3 — PyPI
- `.github/workflows/publish.yml`:
  - Trigger: tag `v*`
  - Build: `python -m build`
  - Publish: `twine upload dist/*`
  - Com OIDC trust (sem API token)

### Ficheiros
- `tests/test_shell.py` — novo
- `tests/test_list_dir.py` — novo
- `tests/test_search_files.py` — novo
- `tests/test_git_tool.py` — novo
- `tests/test_openai_provider.py` — novo
- `tests/test_anthropic_provider.py` — novo
- `tests/test_agent_modes.py` — novo
- `tests/test_translator.py` — novo
- `tests/test_session.py` — novo
- `tests/test_workspace.py` — novo
- `.github/workflows/ci.yml` — novo
- `.github/workflows/publish.yml` — novo

---

## Ordem de Execução

| Sprint | Descrição | Dependências | Testes | Esforço |
|---|---|---|---|---|
| 1 | 4 novas tools | Nenhuma | ~12 novos | 3-4h |
| 2 | OpenAI + Anthropic | Nenhuma | ~6 novos | 3-4h |
| 3 | Modos plan/agent/yolo | Sprint 1 (tools têm is_destructive) | ~4 novos | 2-3h |
| 4 | i18n | Nenhuma | ~3 novos | 2h |
| 5 | TUI avançada | Sprint 3 (modos) | ~4 novos | 5-6h |
| 6 | CLI completo | Sprint 4 (i18n) | ~3 novos | 2-3h |
| 7 | Sessions + Workspace | Sprint 1 (tools), Sprint 3 (agente) | ~4 novos | 3-4h |
| 8 | Testes + CI + PyPI | Todos os sprints | ~10 novos | 3-4h |

---

## Verificação Final

1. `make test` — ≥80% cobertura, todos os testes passam
2. `make lint` — ruff + black + mypy sem erros
3. `make build` — gera wheel + sdist
4. Teste manual: `pydeepseek --provider openai --mode agent`
5. Teste manual: `pydeepseek config` → alterar provider → `pydeepseek`
6. Teste manual: `Ctrl+M` alterna modos visivelmente na TUI
7. Teste manual: `make run` com `LANGUAGE=en_US` mostra interface em inglês
