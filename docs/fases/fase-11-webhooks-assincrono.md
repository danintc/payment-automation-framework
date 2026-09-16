# Fase 11: Webhooks + Testes Assíncronos

## 01. O que você vai aprender
Nesta fase, você vai dominar o teste de fluxos assíncronos em APIs, com foco pesado em **Webhooks**, que são o coração dos sistemas de pagamento modernos (como Pix e gateways de cartão de crédito). Você aprenderá a:
- Lidar com processamentos que não retornam o resultado imediatamente.
- Entender, disparar e validar Webhooks (as "APIs reversas").
- Validar a integridade e segurança de notificações usando assinaturas **HMAC-SHA256**.
- Dominar o `expect.poll()` do Playwright para testes de *polling* (verificação contínua).

## 02. Por que isso importa para um QA
Em um sistema de pagamentos, quando um usuário clica em "Pagar com Pix", a API responde na hora com um QR Code, não com a confirmação do pagamento. A confirmação real só acontece segundos ou minutos depois, quando o banco avisa o gateway, e o gateway avisa o seu sistema via **Webhook**. 

Se você, como SDET, testa apenas a criação do pedido e ignora o fluxo assíncrono (o recebimento do webhook e a consequente atualização do status do pedido no banco de dados), você está deixando a parte mais crítica do negócio vulnerável. Bugs em webhooks significam clientes pagando e não recebendo o produto, ou pior, produtos sendo liberados sem que o pagamento tenha sido efetuado (fraude).

## 03. Pré-requisitos
- Compreensão sólida sobre métodos HTTP (POST, GET).
- Domínio sobre o Playwright APIRequestContext (para fazer requisições).
- Entendimento básico do NodeJS (para usarmos a biblioteca nativa `crypto`).
- Conhecimento sobre Promises e `async/await` em TypeScript.

## 04. Conceitos
- **Webhook (API Reversa):** Ao invés de você perguntar ao servidor "E aí, mudou algo?", o servidor envia uma requisição POST (o webhook) para o seu sistema dizendo "Aconteceu tal coisa!". É movido a eventos (Event-driven).
- **Assincronismo:** É o tempo de "delay" entre a ação inicial e a sua conclusão. Ex: pedir um lanche no iFood é síncrono (pedido aceito), mas a entrega é assíncrona (você será notificado quando chegar).
- **Polling:** Técnica onde o cliente fica fazendo requisições repetidas de tempos em tempos perguntando "Já terminou? Já terminou?" até que o status mude ou ocorra um timeout.
- **HMAC-SHA256 (Hash-based Message Authentication Code):** Uma técnica de criptografia essencial em pagamentos. O gateway envia o webhook junto com um cabeçalho (ex: `x-signature`). Esse cabeçalho contém um hash do *payload* gerado a partir de uma "Chave Secreta" (Secret) que só o gateway e o seu sistema conhecem. Isso garante que o webhook realmente veio do gateway e não foi alterado no meio do caminho por um hacker.

## 05. Explicação mastigada
Imagine a seguinte conversa:
1. **Você (Comprador):** "Me dá um Pix pra eu pagar R$ 50,00."
2. **Seu Sistema (API):** "Aqui está o QR Code! Aguardando o pagamento." (Resposta Síncrona).
3. *(O usuário escaneia e paga no app do banco)*.
4. **Gateway (Stripe/Pagar.me):** "Ei, Seu Sistema! O Pix de R$ 50,00 foi PAGO! (Webhook enviado via POST). E pra provar que sou eu mesmo, o hash desse aviso é `a1b2c3d4`."
5. **Seu Sistema:** Confere se a mensagem geraria o hash `a1b2c3d4` usando a senha secreta. Se bater, atualiza o pedido para "PAID".

Para testar o passo 5 (que é onde moram 90% dos bugs), nós temos duas missões no Playwright:
1. Simular o Gateway, criando o hash HMAC e mandando o POST (webhook) diretamente para o backend.
2. Aguardar (Polling) até que o backend processe essa notificação e mude o status do pedido.

## 06. Exemplos
Para testarmos o webhook, não precisamos depender que o usuário pague de verdade. Nosso teste vai gerar o evento de webhook artificialmente.

### Assinando o Webhook no Teste (HMAC-SHA256)
Usamos o módulo `crypto` do Node para criar a assinatura da mesma forma que o Gateway faria:
```typescript
import crypto from 'crypto';

const payload = { event: 'payment.success', order_id: 123 };
const secret = 'minha_chave_secreta_super_segura';

const hash = crypto
  .createHmac('sha256', secret)
  .update(JSON.stringify(payload))
  .digest('hex'); // Gera algo como '9f86d081884c7d659a2feaa0c55ad015...'
```

### O Polling com Playwright
O Playwright possui a função mágica `expect.poll`. Ela executa uma função em loop até que a condição seja atendida ou dê timeout.
```typescript
await expect.poll(async () => {
    const res = await request.get(`/orders/${orderId}`);
    const json = await res.json();
    return json.status; // Vai continuar rodando até retornar 'PAID'
}).toBe('PAID');
```

## 07. Código comentado

```typescript
import { test, expect } from '@playwright/test';
import crypto from 'crypto';

test.describe('Testes de Webhook de Pagamento', () => {

  test('Deve processar webhook de PIX pago e atualizar status do pedido', async ({ request }) => {
    // 1. Setup: Criamos um pedido no sistema e pegamos o ID (mockado para exemplo)
    const orderId = 'ORD-999888';
    const secretWebhook = 'whsec_test_secret_123'; // Mesma chave que o backend tem configurada

    // 2. Preparamos o payload exato que o Gateway enviaria
    const webhookPayload = {
      id: "evt_12345",
      type: "payment_intent.succeeded",
      data: {
        order_id: orderId,
        amount: 15000, // R$ 150,00
        method: "pix"
      }
    };

    // 3. Geramos a assinatura (HMAC-SHA256) baseada no payload e na chave secreta
    const signature = crypto
      .createHmac('sha256', secretWebhook)
      .update(JSON.stringify(webhookPayload))
      .digest('hex');

    // 4. AÇÃO: Simulamos o envio do Webhook para o nosso backend
    const webhookResponse = await request.post('/api/webhooks/gateway', {
      data: webhookPayload,
      headers: {
        'stripe-signature': signature, // O header de validação
        'Content-Type': 'application/json'
      }
    });

    // O backend deve aceitar a notificação (Geralmente respondem 200 OK rápido para não dar timeout no gateway)
    expect(webhookResponse.status()).toBe(200);

    // 5. VALIDAÇÃO ASSÍNCRONA (Polling): Esperamos que o pedido seja atualizado
    // O backend recebeu o webhook, mas pode levar um tempinho para salvar no banco
    await expect.poll(
      async () => {
        // Consultamos o status do pedido
        const checkOrder = await request.get(`/api/orders/${orderId}`);
        const orderData = await checkOrder.json();
        console.log(`Checando status: ${orderData.status}`);
        return orderData.status;
      },
      {
        message: 'O status do pedido deve mudar para PAID após receber o webhook',
        timeout: 10000, // Espera até 10 segundos
        intervals: [1000, 2000, 3000], // Faz as tentativas nestes intervalos (1s, 2s, 3s...)
      }
    ).toBe('PAID');
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Implemente um teste que simula o webhook de um **Estorno (Refund)**.
1. Crie um payload de webhook com `type: "payment.refunded"`.
2. Gere a assinatura HMAC usando uma chave secreta estática `'super_secret'`.
3. Envie um POST para a rota do seu webhook (ex: `/api/webhooks/gateway`).
4. Valide que o status code do webhook é 200.
5. Use o `expect.poll` consultando o GET do pedido para verificar se o status mudou para `'REFUNDED'`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Fluxo de Pix expirado.
Crie um teste onde:
- O Gateway avisa que o Pix passou do prazo (`type: "pix.expired"`).
- O seu payload precisa ter o número de um pedido.
- Envie o webhook e aguarde (poll) que o pedido no seu sistema passe para o status `'EXPIRED'` ou `'CANCELED'`.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Segurança primeiro (Teste Negativo).
Simule um **ataque Hacker**. Um hacker descobriu o endpoint do seu webhook e tentou enviar um payload de "Pagamento Aprovado", porém ele não possui a *Secret Key*.
- Crie o payload de sucesso.
- Tente enviar a requisição de webhook com um cabeçalho de assinatura genérico (ex: `'assinatura_falsa_do_hacker'`).
- Valide que o backend **rejeita** a requisição com o HTTP Status `401 Unauthorized` ou `403 Forbidden`.
- Verifique que o pedido original no banco de dados **não** teve seu status alterado para pago (o status deve continuar 'PENDING').

## 11. Erros comuns
- **`JSON.stringify` formatações:** O HMAC usa uma *string* para gerar o hash. Se o Gateway usa um JSON compactado, mas seu NodeJS faz um `JSON.stringify` que injeta espaços (ex: `{ "id": 1 }` vs `{"id":1}`), as assinaturas não vão bater e o teste de webhook retornará 401. Cuidado com o `Content-Type`.
- **Não usar Polling:** Tentar consultar o status imediatamente (`await request.get`) logo na linha seguinte do POST. Às vezes o backend leva milissegundos para comitar no banco, fazendo o teste falhar aleatoriamente (flaky test).
- **Timeouts infinitos:** Esquecer de definir um limite razoável no `expect.poll` (o padrão é 5 segundos, às vezes precisamos aumentar usando a config `{ timeout: 15000 }`).

## 12. Debugging
- **Assinatura Rejeitada no Teste:** Se o seu teste não consegue enviar o webhook porque o backend rejeita a assinatura, crie um `console.log` da string exata que está sendo criptografada e compare com a string que o backend recebe. Geralmente é conflito de formatação UTF-8 ou espaços em branco.
- Use sites como [CyberChef](https://gchq.github.io/CyberChef/) (HMAC -> SHA256) com o mesmo payload e secret para ver se a chave gerada pelo seu TypeScript bate com a do site.

## 13. Aplicação no projeto principal
Crie no projeto uma suite dedicada: `tests/api/payments/webhooks.spec.ts`.
Esta suite deve conter testes que cobrem as principais transições de estado do negócio:
- Autorização de cartão de crédito.
- Confirmação de Pix.
- Estorno (Chargeback / Refund).
- Falha na captura (Insufficient Funds).
Esses testes não devem depender de interfaces gráficas. Apenas injetam o evento no motor de estado da API e garantem o resultado no banco.

## 14. Perguntas de entrevista
1. **P:** Qual a diferença de testar uma API síncrona para uma API baseada em Webhooks?
   **R:** Numa síncrona a validação é imediata no Response. Em Webhooks, a validação exige um teste assíncrono (polling) para conferir se o "efeito colateral" do evento atualizou o estado do sistema corretamente.
2. **P:** Como você garante que seu endpoint de Webhook não está vulnerável a fraudes onde qualquer um manda pedidos pagos?
   **R:** Validando que o endpoint exige uma assinatura gerada com chave simétrica (HMAC-SHA256) ou chaves assimétricas, garantindo a autenticidade e a integridade do payload enviado.

## 15. Checklist
- [ ] Entendo a diferença entre fluxo síncrono e assíncrono em pagamentos.
- [ ] Sei construir a assinatura HMAC-SHA256 com `crypto` no NodeJS.
- [ ] Sei enviar requisições injetando cabeçalhos customizados (`headers`).
- [ ] Entendi como evitar flaky tests usando `expect.poll` do Playwright.
- [ ] Fiz os testes negativos garantindo a segurança do endpoint.

## 16. Critério para avançar
Você só deve avançar para a próxima fase se for capaz de simular o recebimento de um Webhook e aguardar que o status de um registro mude via chamada de API (GET) usando o mecanismo de *polling*. Dominar isso é um dos maiores diferenciais de um SDET sênior focado em backends.
