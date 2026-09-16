# Fase 16: Projeto Final SDET

## 01. O que você vai aprender
- Como planejar, arquitetar e implementar um framework completo de automação de testes de API do zero usando Playwright e TypeScript.
- Integração de múltiplos fluxos complexos: criação de pedido, pagamento via Pix, simulação de Webhook (callback) e validação no Banco de Dados.
- Padrões de projeto avançados para testes de API (Data Builders, API Clients, Fixtures customizadas).
- Geração de relatórios e integração contínua simulada (CI/CD).

## 02. Por que isso importa para um QA
O título de "SDET" (Software Development Engineer in Test) exige mais do que apenas escrever scripts isolados. O mercado de pagamentos e fintechs demanda profissionais capazes de construir soluções de teste resilientes e escaláveis que garantam que o dinheiro não se perca no caminho. Dominar a arquitetura completa de um framework prova que você consegue sair do nível tático (executar testes) para o nível estratégico (garantir a confiabilidade da plataforma).

## 03. Pré-requisitos
- Conclusão das Fases 01 a 15.
- Domínio de TypeScript (interfaces, classes, assincronicidade).
- Domínio do Playwright `APIRequestContext`.
- Conhecimento profundo sobre validação de Banco de Dados (PostgreSQL/MongoDB) e simulação de Webhooks.

## 04. Conceitos
- **Framework Architecture**: A espinha dorsal do seu projeto de automação (Pastas, Utils, Configurações).
- **End-to-End API Testing**: Testar não apenas um endpoint, mas o fluxo completo de negócio (ex: Carrinho -> Checkout -> Pagamento Pix -> Conciliação -> Webhook -> Atualização de Status).
- **Data Management**: Criação e limpeza (Teardown) de massa de dados complexa e relacional de maneira automatizada e isolada.

## 05. Explicação mastigada
Pense neste projeto final como o seu TCC (Trabalho de Conclusão de Curso) ou seu "Masterpiece". Você não vai apenas aprender algo novo aqui, você vai **integrar** tudo. 

Até agora, você aprendeu a testar endpoints separadamente, consultar o banco e validar esquemas. No mundo real de pagamentos, um Pix gerado possui um tempo de expiração (`expires_in`), um `txid` único, e requer que um sistema terceiro (o Gateway ou Banco Central) chame sua API (Webhook) para confirmar que o cliente pagou. Se essa esteira quebrar em qualquer ponto, o cliente fica sem o produto ou a empresa fica sem o dinheiro. O seu framework vai automatizar a validação de todas essas peças engrenando juntas.

## 06. Exemplos
**O Fluxo de Negócio que você irá automatizar:**
1. **POST /orders**: Cria um pedido no sistema.
2. **POST /payments/pix**: Gera a cobrança Pix (QR Code e Copy/Paste).
3. **Database Check**: Verifica se o status do pedido está `PENDING` e o `txid` foi salvo.
4. **POST /webhooks/gateway**: O seu teste irá simular o provedor de pagamento enviando um evento `payment.confirmed` para o seu webhook.
5. **Database Check (Final)**: Verifica se o status mudou para `PAID`.

## 07. Código comentado

```typescript
// Exemplo estrutural de como o teste principal E2E do Projeto Final pode se parecer:
import { test, expect } from '@playwright/test';
import { OrderClient } from '../../src/clients/OrderClient';
import { PaymentClient } from '../../src/clients/PaymentClient';
import { WebhookSimulator } from '../../src/utils/WebhookSimulator';
import { DatabaseHelper } from '../../src/db/DatabaseHelper';
import { OrderBuilder } from '../../src/builders/OrderBuilder';

test.describe('E2E Pix Payment Flow', () => {
  let orderId: string;
  let txid: string;

  // Cleanup após o teste para manter a base de dados limpa
  test.afterEach(async () => {
    if (orderId) {
      await DatabaseHelper.deleteOrder(orderId);
    }
  });

  test('Deve processar um pagamento Pix de ponta a ponta com sucesso', async ({ request }) => {
    const orderClient = new OrderClient(request);
    const paymentClient = new PaymentClient(request);
    const db = new DatabaseHelper();

    // 1. Arrange: Construir massa de dados
    const orderPayload = new OrderBuilder().withRandomItems().build();

    // 2. Act: Criar pedido
    const orderResponse = await orderClient.createOrder(orderPayload);
    expect(orderResponse.status()).toBe(201);
    const orderData = await orderResponse.json();
    orderId = orderData.id;

    // 3. Act: Pagar com Pix
    const pixResponse = await paymentClient.payWithPix(orderId);
    expect(pixResponse.status()).toBe(200);
    const pixData = await pixResponse.json();
    txid = pixData.txid;

    // 4. Assert: Banco de Dados deve estar pendente
    let dbOrder = await db.getOrderById(orderId);
    expect(dbOrder.status).toBe('PENDING_PAYMENT');
    expect(dbOrder.txid).toBe(txid);

    // 5. Act: Simular notificação do Webhook (Mock do Gateway)
    const webhookStatus = await WebhookSimulator.sendPixConfirmation(txid, orderData.amount);
    expect(webhookStatus).toBe(200); // Nosso sistema deve aceitar o webhook

    // 6. Assert: Banco de Dados deve estar atualizado como PAGO
    // Dica: Pode ser necessário um poll (espera ativa) se a atualização for assíncrona (RabbitMQ/Kafka)
    await expect.poll(async () => {
      const dbCheck = await db.getOrderById(orderId);
      return dbCheck.status;
    }, {
      timeout: 10000,
    }).toBe('PAID');
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo**: Estruturar a fundação do framework do Projeto Final.

1. Inicialize um novo repositório limpo: `npm init -y` e instale o Playwright: `npm init playwright@latest`.
2. Crie a estrutura de diretórios:
   - `src/clients/` (Classes que abstraem a chamada aos endpoints)
   - `src/db/` (Conexão e queries de banco de dados)
   - `src/builders/` (Padrão Builder para gerar massas de teste dinâmicas)
   - `src/utils/` (Funções auxiliares, Webhook simulators)
   - `tests/e2e/` (Testes de ponta a ponta que varrem múltiplos domínios)
   - `tests/contract/` (Testes de schema JSON)
3. Configure o arquivo `playwright.config.ts` com as `baseURL`s necessárias (API principal, API do webhook) e mapeie variáveis sensíveis de ambiente usando a biblioteca `dotenv`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo**: Implementar os Clientes de API e Builders.

- Crie um `OrderClient` com métodos genéricos como `create(payload)` e `get(id)`.
- Crie um `PaymentClient` com métodos de ações críticas `createPix(orderId)` e `createCreditCard(orderId, cardDetails)`.
- Crie a classe `WebhookSimulator` capaz de fazer um `POST` no endpoint de recepção de webhooks do sistema. Simule perfeitamente o Payload que um Gateway de pagamentos real enviaria, forjando a assinatura (signature) se o sistema exigir validação de HMAC.
- Escreva um teste simples para validar que seus clientes estão conseguindo se comunicar com a API autenticada e recebendo os status codes previstos.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo**: O Desafio de Ouro SDET - Cenários de Falha e Concorrência.

Você já implementou o caminho feliz; a essência da Qualidade de Software está em destruí-lo. Escreva testes robustos para as seguintes anomalias:
1. **Idempotência do Webhook**: Envie o mesmo payload de webhook de confirmação de Pix duas ou mais vezes para o mesmo `txid`. O sistema deve retornar `200 OK`, mas fundamentalmente não deve duplicar o saldo do usuário nem lançar erros `500`. Valide o saldo diretamente no BD.
2. **Pagamento a Menor (Underpayment)**: Simule um webhook de Pix onde o valor pago (`amount`) é inferior ao valor original do pedido. A regra de negócio indica que o sistema deve alterar o status para `PARTIAL_PAYMENT` ou `ERROR`. Garanta que a transação não avance de forma indevida.
3. **Condição de Corrida (Race Condition)**: Tente pagar o mesmo pedido simultaneamente com Cartão de Crédito e Pix (iniciando as chamadas em paralelo com `Promise.all`). A API deve garantir lock otimista ou pessimista no banco de dados, aceitando apenas um dos pagamentos e rejeitando o outro com clareza.

## 11. Erros comuns
- **Hardcodar URLs e Tokens**: Deixar credenciais estáticas espalhadas nos scripts ao invés de centralizar tudo via `.env`.
- **Falta de Isolamento**: Criar testes que falham porque dependem da execução cronológica de testes anteriores (Chain Testing). Cada bloco `test()` no seu projeto final deve ser atômico, determinístico e capaz de rodar em paralelo puro com `test.describe.configure({ mode: 'parallel' })`.
- **Negligenciar o Teardown**: Deixar uma montanha de massa podre (pedidos, usuários fake, carteiras digitais vazias) no banco de dados. Em arquiteturas de pagamentos, inflar o banco degrada a performance da esteira. Limpe a sujeira utilizando os hooks de `afterEach` ou scripts robustos no `teardown` global.

## 12. Debugging
- Ao enfrentar *timeouts* intermitentes durante a validação de Webhooks e Banco de Dados, lembre-se de que os sistemas de pagamento modernos baseiam-se fortemente em arquitetura orientada a eventos (Kafka, SQS, RabbitMQ). Consequentemente, o status da transação não mudará em milissegundos. Utilize a asserção `expect.poll()` do Playwright para realizar um "Wait inteligente", consultando ativamente o banco de dados até que a alteração do status ocorra dentro de um limiar aceitável.
- Habilite e explore o Playwright Tracing (`--trace on`). Em testes de API, os rastros visuais podem não ter screenshots da tela, mas expõem cronologicamente a timeline completa de Requests, Headers, e Bodys transmitidos. Isso ajuda a rastrear a jornada de um Webhook perdido no meio de múltiplos disparos de API.

## 13. Aplicação no projeto principal
Este *é* o seu projeto principal. A conclusão desta fase marca a entrega do seu TCC. A arquitetura que você acabou de estruturar é um portfólio rico, perfeitamente utilizável em uma entrevista técnica de alto padrão. Você fundiu padrões de software modernos à automação QA, validou arquiteturas assíncronas complexas e demonstrou domínio real das integrações em um sistema financeiro.

## 14. Perguntas de entrevista
1. "Seu teste automatizado massifica a criação de pedidos no banco. Como você garante que esses dados fakes não sujem o ambiente produtivo ou afetem negativamente os dashboards financeiros da empresa?"
2. "Como você desenharia a estratégia de automação para um fluxo de pagamento em que a confirmação transacional depende de um processo de análise de fraude externa e pode demorar alguns bons minutos?"
3. "Explique a diferença arquitetônica entre validar um pagamento recebendo um Webhook vs realizando Polling em um endpoint de status de pedido."
4. "Por que adotar abstrações como API Clients (Page Object Model para APIs) no seu framework, ao invés de fazer injeções diretas com `request.post` dentro de todos os blocos `test()` do projeto?"

## 15. Checklist
- [ ] Estrutura do framework base inicializada e segmentada por responsabilidade (Clients, DB, Utils, Builders).
- [ ] Configuração do ecossistema centralizada com `dotenv` e `playwright.config.ts`.
- [ ] Clients de API (OrderClient, PaymentClient, WebhookSimulator) desenhados com métodos bem definidos.
- [ ] Data Builders funcionais para compor massa de testes aleatória de forma limpa.
- [ ] Teste E2E do *Golden Path* (Caminho Feliz) do Pix, desde o pedido até a validação profunda de banco, devidamente codificado e rodando sem *flakes*.
- [ ] Cenários de falha e de concorrência (Edge Cases) via Webhooks implementados e validados.
- [ ] Clean up (teardown) devidamente aplicado para garantir isolamento e higiene dos dados.
- [ ] (Opcional, mas Altamente Recomendado) Pipeline de CI/CD (GitHub Actions / GitLab CI) configurada e capaz de executar o framework headless em eventos de Pull Request.

## 16. Critério para avançar
N/A - Esta é a última fase! Se você concluiu todos os desafios acima e dominou completamente os tópicos, meus parabéns. Você cruzou a linha de chegada e agora exibe as competências consolidadas de um **Engenheiro(a) de Qualidade de Software especializado(a) em APIs de Pagamento usando TypeScript e Playwright (SDET)**. Sucesso no mercado, você está pronto.
