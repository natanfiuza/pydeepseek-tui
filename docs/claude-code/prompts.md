## 2026-05-17

**Frase de teste**

`Crie uma analise completa deste projeto e salve em docs/pydeepseek`
`O que faz esta minha codebase?`

### Feature: APP_DEBUG com logging em ~/.deepseek-tui/sessions

Criar uma nova feature, no .env vamos poder colocar um variavel chamada APP_DEBUG ele tera o valor booleano e default como false, se ele não existir no .env e false, e quando ela for true sera criado um arquivo de log dentro da pasta da session em ~\.deepseek-tui\sessions este arquivo vai gravar tudo que foi recebido pelo usuario, tudo que for exibido, e claro todas as mensagens de erro geradas. E tambem um segundo arquivo que deve ficar na mesma pasta so que este arquivo vai receber um json com todos os prompts e os reasoning_content gerados pela aplicação. Ao final gere um relatório detalhado com as alterações em docs/clude-code/reports 

### Coreção de bugs

Ao executar um comando as mensagens como "A executar list_dir.." estão sendo exibidas sem a formatação de cores e ficam desta forma "[bold yellow]A executar list_dir...[/bold yellow]", verifique isto. E tambem as mensagens de resposta do modelo estão sendo exibidas com varias quebras de linha uma por palavra ficando dificil a leitura, corrija isso. 

### Registro de sessions

Cria feature que vai registrar toda atividade de uma session aberta (session aberta = toda vez que o pydeepseek for executado ou seja ao inicializar), o que seria estas atividades: 
- Arquivo json das interações com o provider de IA, tipo uma memoria, onde vai registrar tambem a quantidade de tokens de input e output e os reasoning content, os prompts gerados, independente se o APP_DEBUG for true este e um log das atividades gerais, remover o log dos prompts quando APP_DEBUG for true e deixar apenas os logs de erro e mensagens exibidas. 
- Dentro da pasta ~/.deepseek-tui/sessions sera criado um arquivo manifest.json nele sera registrado a data de inicio da sessão, o id (que sera um uuid) , datetime da ultima interação. 
- O id da sessão sera o nome da pasta que vai receber os arquivos da sessão incluido o arquivo de log quando APP_DEBUG for true, o arquivo de log json com as interações do provider de IA, entre outros que surgirem durante o desenvolvimento.
- Gravar no arquivo de log json da interção os tokens gastos e o amount dos gastos de token (como vamos iniciar com o deepseek nele existe estes dados na resposta da API).
- Mostrar na tela principal da aplicação na parte superior direita o tempo total da sessão baseado com o registro do arquivo ~/.deepseek-tui/sessions/manifest.json
- Mostrar na tela principal da aplicação na parte superior direita o total de tokens gastos nesta session usando a soma que esta no arquivo gerado na pasta da sessão.
- Mostrar na tela principal da aplicação na parte superior direita o valor total em currency ( a moeda e dollar) do que ja foi gasto nesta sessão.
  