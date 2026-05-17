# Análise do Projeto: `pydeepseek-tui`

Data: 2026-05-15

---

## Visão Geral

É uma **TUI (Terminal User Interface) assíncrona** para interagir com a API do DeepSeek, construída com **Textual** + **Python 3.13**. A aplicação funciona como um agente de IA com capacidade de executar ferramentas (function calling) — pesquisa web, leitura/escrita de ficheiros, e extração de conteúdo de URLs.

---

## Estrutura do Projeto

```
src/pydeepseek_tui/
├── app.py              # UI Textual (App, Header, Footer, Input, RichLog)
├── agent.py            # Orquestrador: loop de chat com suporte a tools
├── cli.py              # Entrada CLI via Click (comando `pydeepseek`)
├── config/
│   ├── auth.py         # Onboarding: pede, encripta e guarda API key (~/.deepseek-tui/.env)
│   ├── crypto.py       # Criptografia via PBKDF2 + Fernet (machine-id binding)
│   └── settings.py     # Dataclass de config, lê .env com dotenv
├── providers/
│   ├── base.py         # Interface abstrata BaseAIProvider
│   ├── deepseek.py     # Implementação via openai.AsyncOpenAI (compatível)
│   └── factory.py      # Factory para instanciar o provider certo
└── tools/
    ├── base.py         # Interface abstrata BaseTool
    ├── file_reader.py  # Lê ficheiros locais
    ├── web_search.py   # Pesquisa DuckDuckGo
    ├── fetch_url.py    # Extrai texto de URLs (httpx + BeautifulSoup)
    ├── write_file.py   # Cria/sobrescreve ficheiros
    └── registry.py     # Registo central + get_core_registry()
tests/
├── test_tools.py       # Testes para FileReaderTool (3 testes)
└── test_agent.py       # Testes para Agent com MockProvider
```

---

## Pontos Fortes

1. **Arquitetura limpa e SOLID** — Separação clara entre UI (`app.py`), lógica de agente (`agent.py`), providers e tools. Cada camada depende de abstrações (`BaseAIProvider`, `BaseTool`), não de implementações concretas.

2. **Factory Pattern** — `ProviderFactory` permite trocar de provider (DeepSeek → OpenAI → Anthropic) sem alterar o resto do código.

3. **Segurança da API Key** — A chave é derivada de um identificador da máquina (usuário + MAC) via PBKDF2 (100k iterações, SHA-256) e encriptada com Fernet. Ficheiro `.env` fica em `~/.deepseek-tui/`.

4. **Streaming + Function Calling** — O `Agent.chat_stream()` faz loop entre streaming de texto e execução de ferramentas, acumulando tool calls parciais do stream até ter os argumentos completos.

5. **Testes com mocks** — `MockProvider` e `MockDelta` simulam o comportamento da API sem rede. Testes cobrem o Agent e uma tool.

6. **Ferramentas úteis** — DuckDuckGo para pesquisa, httpx assíncrono para fetch, BeautifulSoup para extração limpa de texto (remove script/style/nav/etc).

---

## Problemas e Riscos Identificados

### 1. Duas implementações de criptografia conflitantes

- `config/auth.py` — usa `Fernet.generate_key()` guardada em `secret.key`, guarda a chave como `DEEPSEEK_API_KEY=<encrypted>` no `.env`
- `config/crypto.py` — usa PBKDF2 com machine-id, espera ler `DEEPSEEK_API_KEY_ENCRYPTED` do `.env`
- `config/settings.py` — importa `decrypt_key` do `crypto.py` e procura a variável `DEEPSEEK_API_KEY_ENCRYPTED`

**Resultado**: O `auth.py` escreve `DEEPSEEK_API_KEY=...` mas o `settings.py` lê `DEEPSEEK_API_KEY_ENCRYPTED`. Os nomes das variáveis são diferentes. O sistema de onboarding e o de leitura de config são **incompatíveis entre si** — a chave salva pelo onboarding nunca será lida pelo `settings.py`.

### 2. `FileReaderTool` com risco de path traversal

```python
async def execute(self, **kwargs: Any) -> str:
    file_path = kwargs.get("file_path")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()
```

A IA pode ler qualquer ficheiro do sistema (ex: `~/.ssh/id_rsa`, `/etc/passwd`). Não há restrição de caminho.

### 3. `WriteFileTool` com o mesmo risco + potencial de sobrescrita destrutiva

```python
with open(file_path, "w", encoding="utf-8") as file:
    file.write(content)
```

Sobrescreve qualquer ficheiro sem confirmação. A IA poderia corromper ficheiros do projeto ou do sistema.

### 4. Testes muito limitados

- Apenas 4 testes no total (3 para `FileReaderTool`, 1 para `Agent`)
- Nenhum teste para: `WebSearchTool`, `FetchUrlTool`, `WriteFileTool`, `DeepSeekProvider`, `ToolRegistry`, `ProviderFactory`, `Settings`, auth/crypto
- Cobertura real muito abaixo do que o `--cov` sugere

### 5. `anthropic` listado como dependência mas não usado

O `anthropic` SDK está no `PipFile` e `pyproject.toml`, mas não há implementação de provider Anthropic. Apenas o comentário no `factory.py` sugere uso futuro.

### 6. `gitpython` listado como dependência mas não usado

Nenhum ficheiro do projeto importa `git`.

### 7. `rich` listado como dependência mas não usado

O Textual já traz o Rich como dependência interna. O projeto não importa `rich` diretamente.

### 8. Sem tratamento de erro para `ProviderFactory` com provider inexistente

Se o `.env` tiver `IA_PROVIDER=openai`, a app quebra com `ValueError` — mas o `cli.py` não trata esse erro com uma mensagem amigável.

### 9. Sem limite de tamanho do histórico de conversa

`self.conversation_history` cresce indefinidamente. Cada tool call adiciona múltiplas mensagens. Com uso prolongado, pode exceder a janela de contexto do modelo.

### 10. `fetch_url.py` — timeout fixo de 10s

Páginas grandes ou lentas podem falhar. Não há retry.

---

## Recomendações

| Prioridade | Ação |
|---|---|
| **Crítico** | Unificar o sistema de criptografia — `auth.py` e `crypto.py` precisam usar o mesmo formato de variável no `.env` |
| **Alta** | Adicionar restrições de path nas tools `FileReaderTool` e `WriteFileTool` (allowlist de diretórios) |
| **Alta** | Confirmar antes de sobrescrever em `WriteFileTool` |
| **Média** | Remover dependências não usadas (`anthropic`, `gitpython`, `rich`) ou implementar os providers |
| **Média** | Adicionar limite de histórico com sumarização ou sliding window |
| **Média** | Expandir cobertura de testes |
| **Baixa** | Melhorar tratamento de erro no CLI para provider inválido |

---

## Conclusão

No geral, o projeto tem uma base arquitetural sólida e bem pensada, com boa separação de responsabilidades e uso de padrões como Factory e abstrações. No entanto, precisa de correções de segurança (path traversal, conflito de criptografia) e consolidação (testes, dependências não usadas) antes de ser considerado pronto para uso em produção.
