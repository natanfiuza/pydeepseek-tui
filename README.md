
# PyDeepSeek TUI 🚀

Uma interface de terminal (TUI) moderna, assíncrona e altamente extensível para interagir com a IA do DeepSeek, construída com Python e Textual.

## 🌟 Principais Funcionalidades

- **Design Responsivo no Terminal:** UI elegante construída com Textual.
- **Function Calling (Agente Autônomo):** A IA consegue pesquisar na web, extrair texto de sites e ler/escrever ficheiros locais.
- **Arquitetura Limpa (SOLID):** Código modular, altamente testável e com baixo acoplamento.
- **Segurança:** A chave da API é encriptada localmente usando a biblioteca `cryptography`.

## 🛠️ Como Instalar e Usar

Certifique-se de ter o Python 3.11+ e o `pipenv` instalados.

1. Clone o repositório e entre na pasta.
2. Instale as dependências:
   ```bash
   make install

   ```

3. Inicie a aplicação (na primeira execução, o sistema irá pedir e encriptar a tua chave da API):

   ```bash
   make run

   ```

## 🧪 Testes

Para correr a bateria de testes automatizados (com suporte a mocks assíncronos):

```bash
make test

```
