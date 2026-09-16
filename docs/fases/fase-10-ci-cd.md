# Fase 10: CI/CD - Pipelines e Automação

## 01. O que você vai aprender
- O que é CI/CD e como integrar seus testes de API do Playwright no GitHub Actions.
- Como subir um ambiente completo (API + Banco de Dados) usando `docker-compose` dentro da pipeline.
- Como configurar a pipeline para rodar os testes a cada Pull Request (PR) e bloquear o merge em caso de falha.
- Como gerar, armazenar e visualizar relatórios de teste (Playwright HTML Report) diretamente no GitHub Actions.
- Práticas de mercado para pipelines focadas em sistemas de pagamento (isolamento, segurança de secrets e testes em paralelo).

## 02. Por que isso importa para um QA
Escrever testes que rodam apenas na sua máquina não garante a qualidade contínua de um sistema. Em gateways de pagamento, um *commit* aparentemente inofensivo pode quebrar o fluxo de liquidação do Pix ou o disparo de webhooks. A pipeline de CI (Continuous Integration) é o seu "guarda-costas". Ela garante que **nenhum código vai para produção** sem passar pela sua suíte automatizada. Um QA Sênior não apenas escreve testes, mas orquestra como e quando esses testes são executados de forma autônoma para proteger a receita da empresa.

## 03. Pré-requisitos
- Ter o repositório de testes com Playwright e TypeScript rodando localmente (Fases anteriores).
- Ter o `docker-compose.yml` da nossa API de pagamentos configurado.
- Conhecimento básico sobre Git (commit, push, pull request).
- Uma conta no GitHub.
- Conhecimentos básicos de YAML (formato usado no GitHub Actions).

## 04. Conceitos
- **CI (Continuous Integration)**: A prática de integrar código frequentemente em um repositório compartilhado. Cada integração é verificada por um build automatizado e testes.
- **Pipeline**: Um conjunto automatizado de passos que o código percorre. Ex: Clonar código -> Instalar dependências -> Subir Banco de Dados -> Rodar API -> Rodar Testes -> Publicar Report.
- **GitHub Actions**: A plataforma de CI/CD nativa do GitHub. Funciona à base de *workflows* configurados em arquivos YAML dentro da pasta `.github/workflows`.
- **Artifacts**: Arquivos gerados durante a pipeline que você deseja guardar e baixar depois, como o relatório HTML do Playwright.
- **Branch Protection Rules**: Configurações no GitHub que impedem que um Pull Request seja "mergeado" se os *status checks* (nossos testes) falharem.

## 05. Explicação mastigada

Imagine que seu projeto seja um restaurante de fast food focado em pagamentos rápidos. O desenvolvedor é quem cria a nova receita (o código). O GitHub é o balcão. E a Pipeline de CI é o Gerente de Controle de Qualidade (você).

Antes dessa receita nova ir para os clientes (Produção), o Gerente obriga que ela seja preparada na cozinha de testes (Pipeline).
1. A pipeline clona o balcão (`actions/checkout`).
2. Traz os ingredientes necessários: instala o Node.js (`actions/setup-node`) e roda `npm ci`.
3. Prepara o forno e liga os sistemas: levanta o PostgreSQL e a API usando `docker-compose up -d`.
4. Degusta a comida: Roda o `npx playwright test`.
5. Dá a nota final: Se a comida estiver ruim (teste falhar), o Gerente grita "NÃO!" e proíbe a receita de ir para o menu (bloqueia o PR). Se estiver boa, ele gera um certificado de qualidade (Artifact / Report) e aprova a receita.

Fazer isso no GitHub Actions exige criar um arquivo `.yml`. É como uma receita de bolo literal: "faça X", depois "faça Y", com comandos de terminal.

## 06. Exemplos

### Estrutura básica de um workflow para Playwright
Este é um arquivo `playwright.yml` que vai dentro da pasta `.github/workflows/`.

```yaml
name: Playwright API Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    timeout-minutes: 60
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: lts/*
        
    - name: Install dependencies
      run: npm ci
      
    - name: Install Playwright Browsers (Se houver testes UI/BFF)
      run: npx playwright install --with-deps
      
    - name: Run Playwright tests
      run: npx playwright test
      
    - name: Upload Report
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 30
```

## 07. Código comentado

Vamos ver como ficaria a pipeline **focada no nosso sistema de pagamentos**, onde precisamos levantar o banco de dados e a API localmente via Docker antes de rodar os testes:

```yaml
# .github/workflows/payment-api-tests.yml
name: API Payment Tests CI

on:
  pull_request:
    branches: [ main, develop ] # Roda sempre que houver um PR para a main ou develop

jobs:
  api-tests:
    runs-on: ubuntu-latest # Executa num servidor Linux fornecido pelo GitHub
    
    # Variáveis de ambiente que a API e o Playwright vão precisar
    env:
      DB_HOST: localhost
      DB_USER: admin
      DB_PASSWORD: supersecretpassword
      DB_NAME: payments_db
      API_URL: http://localhost:3000

    steps:
      # Passo 1: Baixar o código do repositório
      - name: Checkout Repo
        uses: actions/checkout@v4

      # Passo 2: Preparar o Node.js
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm' # Agiliza a instalação cacheando dependências

      # Passo 3: Instalar as dependências do projeto
      - name: Install Dependencies
        run: npm ci

      # Passo 4: Subir a infraestrutura (PostgreSQL + API Mock)
      # O "-d" roda em background para a pipeline poder continuar para o próximo passo
      - name: Start Database and API
        run: docker-compose -f docker-compose.ci.yml up -d

      # Passo 5: Esperar a API ficar saudável antes de rodar os testes (Wait for-it)
      - name: Wait for API to be Ready
        run: |
          npx wait-on http://localhost:3000/health -t 30000
          echo "API is up and running!"

      # Passo 6: Rodar os testes automatizados do Playwright
      - name: Run Playwright API Tests
        run: npx playwright test --project=api-tests

      # Passo 7: Exibir os logs do docker-compose se os testes falharem (Ótimo para debug)
      - name: Show Docker Logs on Failure
        if: failure()
        run: docker-compose -f docker-compose.ci.yml logs

      # Passo 8: Fazer upload do relatório do Playwright (mesmo se falhar)
      - name: Upload HTML Report
        uses: actions/upload-artifact@v4
        if: always() # O if: always() garante que o report seja gerado, independentemente do resultado dos testes
        with:
          name: api-payment-test-report
          path: playwright-report/
          retention-days: 7 # Guarda o report por 7 dias para economizar espaço
```

## 08. Exercício guiado (Nível 1 - Guided)

**Objetivo:** Criar sua primeira pipeline no GitHub Actions.

**Passo a passo:**
1. Na raiz do seu projeto local, crie a estrutura de diretórios: `mkdir -p .github/workflows`
2. Crie o arquivo `ci.yml`: `touch .github/workflows/ci.yml`
3. Cole o código simplificado da seção 06 no arquivo `ci.yml`.
4. Faça commit dessas mudanças:
   ```bash
   git add .github/workflows/ci.yml
   git commit -m "chore: setup github actions CI"
   git push origin main
   ```
5. Acesse seu repositório no GitHub, vá até a aba **Actions**.
6. Você verá seu workflow rodando. Clique nele para ver os *logs* em tempo real.
7. Se passar, ficará verde. Clique nos Artifacts no fim da tela para baixar o `playwright-report.zip`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)

**Objetivo:** Integrar o Docker Compose na sua pipeline para testar a API com um banco real efêmero.

1. No repositório, crie um branch chamado `feature/ci-docker`.
2. Edite seu arquivo `.github/workflows/ci.yml`.
3. Adicione o *step* para subir o `docker-compose up -d`. Lembre-se que o runner do GitHub Actions já tem o Docker e o `docker-compose` instalados por padrão.
4. Adicione um *step* que use o `npx wait-on` (ou comando `curl` com `sleep`) aguardando a rota de *health check* da sua API de pagamentos (ex: `http://localhost:3000/health`).
5. Faça *push* desse branch.
6. Crie um Pull Request para a `main`.
7. Observe o status do PR. Ele deve mostrar o GitHub Actions rodando o *check*.

## 10. Desafio (Nível 3 - Challenge)

**Objetivo:** Bloquear o PR se os testes falharem e configurar relatórios detalhados.

1. **Quebrar a API de propósito:** No branch `feature/ci-docker`, altere algo na sua API (ou no mock) que você sabe que fará o teste de criação de Pix falhar (ex: mude o status HTTP esperado de 201 para 500).
2. Faça o push. No GitHub, o check do PR ficará vermelho ❌.
3. **Configurar Branch Protection Rule:**
   - No repositório do GitHub, vá em **Settings** -> **Branches**.
   - Adicione uma regra para a branch `main`.
   - Marque a opção: "Require status checks to pass before merging".
   - Procure pelo nome do seu job do GitHub Actions (ex: `api-tests`) e torne-o obrigatório.
4. Tente "mergear" o PR. O GitHub não deve deixar! O botão de Merge deve ficar desabilitado.
5. **Corrija o erro:** Arrume a API de volta ao normal, faça push. A pipeline roda de novo, fica verde, e desbloqueia o PR.

## 11. Erros comuns

- **Esquecer o `if: always()` no step de upload do report.** Se um teste falha, a pipeline para (exit code 1). Os passos seguintes são cancelados. Se não puser `always()`, você perde o report de falha (justamente o que mais importa).
- **Problemas de conectividade com localhost:** O GitHub Actions roda num Ubuntu. Usar `localhost` no `.env` funciona perfeitamente para conectar a API levantada pelo Docker na porta exposta para a rede "host".
- **Falta de tempo de espera (Race Conditions):** O `docker-compose up -d` retorna imediatamente, mas o banco de dados (ex: PostgreSQL) pode demorar uns segundos para aceitar conexões. A API tentará conectar, falhará, e quando o Playwright rodar, nada vai funcionar. Use sempre scripts de *wait-on* para garantir que tudo está vivo e saudável.
- **Vazar tokens/chaves de API no log:** Evite usar `console.log` de payloads completos de pagamento que contenham tokens de sandbox expostos. Use GitHub Secrets se precisar acessar APIs externas.

## 12. Debugging

- **Baixe o report zipado:** Ele contém o trace (`trace.zip`). No seu terminal local, rode `npx playwright show-trace path/to/trace.zip` para ver exatamente a resposta da API (Headers, Body) no momento do erro lá no container do GitHub Actions.
- **Debugando containers no Actions:** Se os testes falharam porque a API quebrou, adicione um step no YAML com `if: failure()` para dar um `docker-compose logs`. Isso imprimirá o log da sua API no console do GitHub, permitindo que você veja o `StackTrace` ou o erro de banco de dados.
- **Tmate (SSH no runner):** Se você estiver muito perdido, existe uma Action chamada `mxschmitt/action-tmate` que abre um SSH diretamente dentro do servidor do GitHub Actions para você debugar manualmente!

## 13. Aplicação no projeto principal

No nosso projeto de **Gateway de Pagamento**, aplicaremos a pipeline para:
1. Ao abrir um PR para qualquer alteração no código da API de Pagamentos.
2. Subiremos uma base limpa de PostgreSQL em Docker na Pipeline (evitando sujar a base de dev/stage).
3. Rodaremos os testes de:
   - Geração de cobrança Pix e Cartão.
   - Disparo simulado de webhooks (notificando o *merchant*).
   - Validação dos status HTTP e contratos via Playwright API Request.
4. Garantiremos que *features* de pagamento não quebrem e que o relatório HTML de testes esteja visível para a equipe de devs baixar via *Artifacts*.

## 14. Perguntas de entrevista

1. **Como você evita que código com bug vá para produção?**
   *Resposta esperada:* Através da configuração de pipelines de CI/CD que rodam nossa suíte do Playwright em todo Pull Request, atrelado às "Branch Protection Rules" (ex: no GitHub) que bloqueiam o botão de merge se o job falhar.
2. **Como você lida com banco de dados em testes na CI?**
   *Resposta esperada:* Geralmente uso containers Docker. Antes dos testes rodarem na pipeline, executamos um `docker-compose up -d` com uma imagem limpa do banco de dados, rodamos as migrações/seeders, e executamos os testes de API. Assim garantimos ambiente isolado e livre de flakiness causado por sujeira de dados.
3. **Se o teste do Playwright falha na pipeline, mas você não tem acesso visual, como você resolve?**
   *Resposta esperada:* Eu garanto que minha pipeline faça o upload do HTML Report ou Traces gerados pelo Playwright como um *artifact* do CI, usando a cláusula `if: always()`. Depois eu baixo o artefato localmente, e uso o Playwright Trace Viewer para debugar com detalhes sobre requests, tempos e respostas.

## 15. Checklist

- [ ] Tenho uma pasta `.github/workflows` criada.
- [ ] O arquivo `yaml` foi configurado e ativa no evento de `pull_request` ou `push`.
- [ ] O Node.js e as dependências (`npm ci`) são instalados na pipeline.
- [ ] A infra (API + DB) é levantada no CI antes dos testes (via Docker).
- [ ] Há um mecanismo de espera (*wait-on*) garantindo que a API está viva.
- [ ] Os testes rodam com sucesso de ponta a ponta na nuvem.
- [ ] O Artifact Report está sendo salvo e pode ser baixado.
- [ ] A branch `main` está protegida requerendo sucesso na pipeline.

## 16. Critério para avançar

Para concluir esta fase, você deve ser capaz de mostrar um Pull Request no seu repositório pessoal onde os testes do Playwright rodaram automaticamente. E, melhor ainda, ter um PR rejeitado propositalmente porque o Playwright flagrou que você quebrou o fluxo de Pix na API, evidenciando o poder do CI/CD como guardião da qualidade.
