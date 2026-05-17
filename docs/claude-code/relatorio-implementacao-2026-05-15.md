# Relatório de Implementação — pydeepseek-tui

**Data**: 2026-05-15
**Base**: [Análise do Projeto](../analise-projeto.md)
**Plano**: [Plano de Desenvolvimento](../../../.claude/plans/serene-cooking-fox.md)

---

## Sumário Executivo

Implementação de 7 fases de melhorias no projeto pydeepseek-tui, cobrindo correções críticas de segurança e criptografia, limpeza de dependências, expansão de testes e otimizações de arquitetura. Resultado: **33/33 testes passam**, cobertura subiu de **43% para 58%**, lint limpo.

---

## Fase 1: Corrigir Criptografia (Crítico)

### Problema
Dois sistemas de criptografia incompatíveis coexistiam no projeto:

| Ficheiro | Método | Variável .env |
|---|---|---|
| `auth.py` | Fernet com chave aleatória | `DEEPSEEK_API_KEY=<enc>` |
| `crypto.py` | PBKDF2 + machine-id | `DEEPSEEK_API_KEY_ENCRYPTED` |

O `auth.py` escrevia `DEEPSEEK_API_KEY` mas o `settings.py` lia `DEEPSEEK_API_KEY_ENCRYPTED`. A chave salva pelo onboarding nunca era lida — **a app não funcionava após o primeiro arranque**.

### Alterações

**Eliminado** `src/pydeepseek_tui/config/auth.py`
- Continha ~57 linhas de lógica de onboarding com sistema de encriptação próprio

**Reescrito** `src/pydeepseek_tui/cli.py`
- Adicionadas funções `_load_decrypted_api_key()` e `_save_encrypted_api_key()` que usam `encrypt_key`/`decrypt_key` do `crypto.py`
- `ensure_api_key()` faz onboarding com `click.prompt(hide_input=True)`, encripta com PBKDF2, escreve variável `DEEPSEEK_API_KEY_ENCRYPTED` no `.env`
- Adicionado `try/except ValueError` para tratamento amigável de provider inválido

**Simplificado** `src/pydeepseek_tui/config/settings.py`
- Removida a dependência de `crypto.py` (a descriptografia agora é feita exclusivamente no `cli.py`)
- `deepseek_api_key` passou a ser lido de `os.environ.get("DEEPSEEK_API_KEY")` injetado pelo CLI
- Mantém leitura de outras configs (`IA_PROVIDER`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`) do `.env`

**Eliminado** `src/pydeepseek_tui/config.py`
- Ficheiro órfão com 21 linhas da versão antiga (classe `Config` não usada)

### Fluxo Final

```
cli.py (onboarding) → crypto.encrypt_key() → .env (DEEPSEEK_API_KEY_ENCRYPTED)
cli.py (arranque)   → crypto.decrypt_key() → os.environ["DEEPSEEK_API_KEY"]
settings.py          → os.environ.get()     → Settings.deepseek_api_key
DeepSeekProvider     → settings.deepseek_api_key
```

---

## Fase 2: Sandbox de Ficheiros (Segurança)

### Problema
`FileReaderTool` e `WriteFileTool` aceitavam qualquer caminho absoluto, permitindo que a IA lesse ficheiros sensíveis (`~/.ssh/id_rsa`, `/etc/passwd`) ou escrevesse em localizações arbitrárias do sistema.

### Alterações

**Criado** `src/pydeepseek_tui/tools/sandbox.py` (13 linhas)
```python
def is_path_allowed(file_path: str, allowed_dirs: list[str] | None = None) -> bool
```
- Usa `os.path.realpath()` para resolver symlinks e `..`
- Usa `os.path.commonpath()` para verificar que o caminho está dentro da allowlist
- Allowlist padrão: `[os.getcwd()]`
- Trata `ValueError`/`OSError` para caminhos inválidos

**Atualizado** `src/pydeepseek_tui/tools/file_reader.py`
- Adicionada validação `is_path_allowed()` antes do `open()`
- Mensagem de erro clara quando bloqueado: "Erro de seguranca: O ficheiro está fora do diretorio de trabalho"

**Atualizado** `src/pydeepseek_tui/tools/write_file.py`
- Adicionada validação `is_path_allowed()` antes da escrita
- Novo parâmetro `overwrite` (boolean, default `false`)
- Se o ficheiro existe e `overwrite=false`, retorna erro pedindo confirmação explícita

---

## Fase 3: Limpeza de Dependências

### Problema
Três dependências listadas mas nunca importadas no código:
- `anthropic` — SDK para Claude, não implementado
- `gitpython` — sem uso
- `rich` — já incluído pelo Textual como dependência transitiva

### Alterações

| Ficheiro | Alteração |
|---|---|
| `PipFile` | Removidos `anthropic`, `gitpython`, `rich` de `[packages]` |
| `pyproject.toml` | Removidos da lista `dependencies` |
| `PipFile.lock` | Regenerado com `pipenv lock` |

Adicionado `pytest-asyncio` aos `dev-packages` para suporte a testes assíncronos.

---

## Fase 4: Limite de Histórico de Conversa

### Problema
`Agent.conversation_history` crescia indefinidamente. Cada tool call adiciona 3+ mensagens. Com uso prolongado, ultrapassaria a janela de contexto do modelo (128K tokens).

### Alterações

**Atualizado** `src/pydeepseek_tui/agent.py`
- Constante `MAX_HISTORY_MESSAGES = 50`
- Método `_trim_history()` com sliding window:
  - Preserva sempre `conversation_history[0]` (system message)
  - Mantém as últimas `MAX_HISTORY_MESSAGES - 1` mensagens
  - Remove mensagens mais antigas do meio
- Chamado após cada ciclo de tool calls
- Yield de aviso `[dim]` quando o histórico é truncado pela primeira vez
- Flag `_history_was_trimmed` evita spam de avisos

---

## Fase 5: Tratamento de Provider Inválido

### Problema
Se `IA_PROVIDER=openai` no `.env`, `ProviderFactory.get_provider()` lançava `ValueError` sem tratamento, resultando em traceback pouco amigável.

### Alterações

**Atualizado** `src/pydeepseek_tui/cli.py`
```python
try:
    app = PyDeepSeekApp()
    app.run()
except ValueError as e:
    click.secho(f"Erro: {e}", fg="red", bold=True)
    click.echo("Verifique a configuracao IA_PROVIDER no ficheiro .env")
    raise SystemExit(1)
```

---

## Fase 6: Expandir Testes

### Antes
4 testes em 2 ficheiros, cobertura 43%.

### Depois
33 testes em 7 ficheiros, cobertura 58%.

| Ficheiro | Testes | Cobre |
|---|---|---|
| `tests/test_sandbox.py` | 6 | `is_path_allowed`: dentro/fofa do cwd, path traversal, múltiplos dirs, default |
| `tests/test_file_writer.py` | 6 | Escrita com sucesso, fora do sandbox, ficheiro existe sem/com overwrite, missing params, cria dirs |
| `tests/test_registry.py` | 6 | Registo, duplicado, missing, schema vazio, formato, nomes |
| `tests/test_factory.py` | 2 | Provider deepseek, provider inválido |
| `tests/test_crypto.py` | 3 | Roundtrip encrypt/decrypt, output base64, decrypt inválido |
| `tests/test_agent.py` | 6 | Streaming, tool calling, streaming tool call, system message, trim history, trim no-op |
| `tests/test_tools.py` | 4 | File reader: sucesso, missing path, not found, sandbox blocked |

### Técnicas de Mock usadas
- `MockProvider` — simula streaming de texto
- `MockProviderWithToolCall` — simula tool call + resposta (com contador de chamadas para evitar loop infinito)
- `MockProviderWithToolCallStreaming` — simula tool call fragmentado (3 chunks)
- `MockDelta` / `MockToolCall` / `MockFunction` — simulam objetos da API
- `monkeypatch.setattr` — substitui `is_path_allowed` nos testes de tools
- `monkeypatch.setenv` + `importlib.reload` — injeta `DEEPSEEK_API_KEY` antes do carregamento de settings

---

## Fase 7: Outras Melhorias

### `fetch_url.py` — Retry
- Extraída função `_fetch()` com lógica de retry
- 2 tentativas, backoff de 2s com `asyncio.sleep`
- Separação entre erro de rede (com retry) e erro de parsing (sem retry)

### `app.py` — Emoji Removido
- Substituído `"a pensar e trabalhar... 🤔"` por `"a pensar e trabalhar..."`
- O emoji não renderiza em todos os terminais Windows/Linux

### `deepseek.py` e `base.py` — `close()`
- Adicionado `async def close()` ao `DeepSeekProvider` que fecha o `AsyncOpenAI`
- Adicionado stub `async def close()` ao `BaseAIProvider` (método opcional, não abstrato)

---

## Impacto por Ficheiro

| Ficheiro | Estado | Linhas |
|---|---|---|
| `src/pydeepseek_tui/config/auth.py` | Eliminado | -57 |
| `src/pydeepseek_tui/config.py` | Eliminado | -21 |
| `src/pydeepseek_tui/cli.py` | Reescrito | 68 |
| `src/pydeepseek_tui/config/settings.py` | Simplificado | 41 |
| `src/pydeepseek_tui/config/crypto.py` | Inalterado | 22 |
| `src/pydeepseek_tui/agent.py` | Reescrito | 113 |
| `src/pydeepseek_tui/tools/sandbox.py` | Novo | 17 |
| `src/pydeepseek_tui/tools/file_reader.py` | Atualizado | 55 |
| `src/pydeepseek_tui/tools/write_file.py` | Reescrito | 80 |
| `src/pydeepseek_tui/tools/fetch_url.py` | Reescrito | 82 |
| `src/pydeepseek_tui/providers/base.py` | Atualizado | +4 |
| `src/pydeepseek_tui/providers/deepseek.py` | Atualizado | +5 |
| `src/pydeepseek_tui/app.py` | Atualizado | 1 linha |
| `PipFile` | Atualizado | -3 deps, +1 dev-dep |
| `pyproject.toml` | Atualizado | -3 deps |
| `PipFile.lock` | Regenerado | — |
| `tests/test_sandbox.py` | Novo | 31 |
| `tests/test_file_writer.py` | Novo | 59 |
| `tests/test_registry.py` | Novo | 70 |
| `tests/test_factory.py` | Novo | 23 |
| `tests/test_crypto.py` | Novo | 19 |
| `tests/test_agent.py` | Expandido | 225 |
| `tests/test_tools.py` | Atualizado | 65 |

---

## Verificação Final

```
$ pipenv run pytest -v
============================= 33 passed in 3.59s ==============================

$ pipenv run ruff check .
All checks passed!

Cobertura: 58% (era 43% antes das alterações)
```

---

## Riscos Residuais

1. **Sandbox limitado ao cwd** — A allowlist padrão é `[os.getcwd()]`. Se o utilizador quiser que a IA aceda a ficheiros noutro diretório, será necessário configurar diretórios adicionais.

2. **Cobertura em 58%** — `app.py` (0%), `cli.py` (0%), `fetch_url.py` (29%), `web_search.py` (41%) e `deepseek.py` (48%) permanecem com cobertura baixa. Estas requerem testes de integração ou mocks mais elaborados.

3. **Compatibilidade Windows** — `crypto.py` usa `uuid.getnode()` que retorna o MAC address. Em Windows, o MAC pode mudar se o adaptador de rede for trocado, invalidando a chave encriptada.
