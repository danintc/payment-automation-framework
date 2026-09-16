# Fase 3: Playwright API - O Básico ao Avançado

## 01. O que você vai aprender
- O que é o `APIRequestContext` no Playwright e como ele funciona por baixo dos panos.
- Como realizar chamadas HTTP (GET, POST, PUT, DELETE) focadas em APIs de pagamento (ex: criar cobranças, consultar status Pix).
- Como validar respostas usando asserções poderosas e embutidas (`expect`).
- Estratégias de manipulação de headers, tokens de autenticação (Bearer, API Keys) e query parameters no contexto de um gateway de pagamento.
- Leitura e validação do payload de resposta JSON.

## 02. Por que isso importa para um QA
Testar APIs de pagamento exige confiança absoluta. Um falso positivo em um teste de checkout pode significar milhões em prejuízo. O Playwright não é apenas uma ferramenta de E2E UI; ele possui uma API interna extremamente rápida e robusta para testes de integração. Como SDET, dominar o `APIRequestContext` permite que você crie testes velozes, evite a instabilidade da UI e valide diretamente as regras de negócio no backend, como fluxos de autorização de cartão, cancelamento de transações e conciliação de saldos.

## 03. Pré-requisitos
- Conhecimentos da Fase 1 e 2 (Setup do Playwright e conceitos de TypeScript).
- Entendimento básico dos verbos HTTP e códigos de status (ex: 200 OK, 201 Created, 400 Bad Request, 422 Unprocessable Entity).
- Compreensão básica do que é um Gateway de Pagamento e formatos de dados como JSON.

## 04. Conceitos
- **APIRequestContext**: A classe do Playwright responsável por gerenciar e disparar requisições HTTP. Ela reutiliza o contexto de rede, podendo inclusive compartilhar cookies e estado de autenticação de uma sessão de UI, se necessário.
- **Request Configuration**: Configurações adicionais enviadas na requisição, como cabeçalhos (`headers`), corpo da mensagem (`data`), e parâmetros de URL (`params`). Em pagamentos, isso frequentemente envolve chaves de idempotência (Idempotency-Key) e assinaturas criptográficas.
- **Assertions (`expect`)**: O motor de validações do Playwright. Trabalha maravilhosamente com os objetos de resposta nativos, permitindo verificar não apenas status code, mas a estrutura completa de um JSON, chaves específicas e performance.

## 05. Explicação mastigada
Imagine que o `APIRequestContext` (geralmente acessado via `request` nos testes) é um carteiro extremamente eficiente. Você entrega a ele um pacote (sua requisição: "Vá ao gateway e crie um Pix de R$ 50,00").
Você precisa dizer:
- **Onde ir (URL):** `/v1/payments/pix`
- **Como ir (Method):** POST
- **O que entregar (Body/Data):** O JSON com valor, chave Pix e descrição.
- **Quem está mandando (Headers):** Sua credencial secreta de acesso (API Key).

O carteiro vai e traz a resposta. A resposta (`APIResponse`) contém o código dizendo se deu certo (201 Created), o comprovante do que foi feito (o JSON de retorno com o QRCode) e os recibos de quem atendeu (Headers da resposta).
Por fim, usamos o `expect` para inspecionar esse pacote de retorno e garantir que não veio uma pedra no lugar do QRCode.

## 06. Exemplos
**Cenário:** Gerar uma cobrança PIX via API.

```typescript
// Exemplo isolado
const response = await request.post('https://api.pagamentos.com.br/v1/cob', {
  headers: {
    'Authorization': `Bearer ${process.env.API_TOKEN}`,
    'Content-Type': 'application/json'
  },
  data: {
    calendario: { expiracao: 3600 },
    devedor: { cpf: '12345678909', nome: 'João da Silva' },
    valor: { original: '150.00' },
    chave: 'suporte@empresa.com.br'
  }
});
```

Validando a resposta:
```typescript
expect(response.status()).toBe(201);
const body = await response.json();
expect(body).toHaveProperty('txid');
expect(body.pixCopiaECola).toContain('000201010211');
```

## 07. Código comentado

```typescript
import { test, expect } from '@playwright/test';

// O Playwright injeta o objeto 'request' automaticamente (instância de APIRequestContext)
test('Deve autorizar uma transação de cartão de crédito com sucesso', async ({ request }) => {
  // 1. Definição do payload da transação
  const transactionPayload = {
    amount: 5000, // Valor em centavos (R$ 50,00) - padrão em gateways para evitar erros de ponto flutuante
    currency: 'BRL',
    payment_method: 'credit_card',
    card: {
      number: '4111111111111111', // Cartão de teste universal (sucesso)
      expiration_month: '12',
      expiration_year: '2028',
      cvv: '123'
    }
  };

  // 2. Disparando a requisição POST
  const response = await request.post('https://api.sandbox.gateway.com/v1/transactions', {
    headers: {
      'Authorization': 'Basic ' + Buffer.from('sk_test_123456:').toString('base64'),
      'Idempotency-Key': `test-charge-${Date.now()}` // Garante que retentativas não cobrem em duplicidade
    },
    data: transactionPayload
  });

  // 3. Asserções (Validações)
  // Garantimos que a API aceitou e processou (201 Created)
  expect(response.status()).toBe(201);
  
  // Convertendo o buffer de resposta em um objeto JSON
  const responseBody = await response.json();

  // Validando regras de negócio vitais
  expect(responseBody.status).toBe('authorized');
  expect(responseBody.amount).toBe(5000);
  expect(responseBody).toHaveProperty('authorization_code');
  expect(responseBody).toHaveProperty('id');
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Consultar o status de uma transação recém-criada (GET).

**Passo a passo:**
1. Crie um novo arquivo `tests/transactions-api.spec.ts`.
2. Escreva um teste `test('Consultar status da transação')`.
3. Use `request.get()` apontando para `/v1/transactions/txn_123`.
4. Passe o header de `Authorization`.
5. Valide que o status code é `200`.
6. Valide que o campo `status` no JSON é `'paid'`.

*Template para começar:*
```typescript
import { test, expect } from '@playwright/test';

test('Deve consultar uma transação paga', async ({ request }) => {
  const transactionId = 'txn_789012'; // Simulação
  // Seu código aqui: const response = await request.get(...)
});
```

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Tentar criar um estorno (Refund) de um valor maior que o saldo da transação.
- **Endpoint:** POST `/v1/transactions/{id}/refund`
- **Body:** `{ "amount": 100000 }` (estorno de mil reais)
- **Regra de negócio esperada:** A API deve recusar.
- **Validação:** Verifique se o status code é `422` ou `400` e se a mensagem de erro diz algo como `"Refund amount exceeds transaction amount"`.
*Dica:* Crie uma transação de R$ 50 primeiro, pegue o ID, e depois tente estornar R$ 100 usando esse ID.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Validar concorrência e Idempotência.
- Escreva um teste que dispare a MESMA requisição de captura de pagamento (POST) duas vezes ao mesmo tempo (utilize `Promise.all`).
- Envie no header `'Idempotency-Key': 'chave-fixa-desafio-01'`.
- **Resultado esperado:** A primeira requisição deve realizar a cobrança e retornar status 201. A segunda deve ser identificada pelo gateway como duplicada e retornar os mesmos dados da primeira, sem cobrar o cliente novamente (muitos gateways retornam 200 OK ou 201 com o mesmo ID). Crie as asserções para garantir que ambas retornam o **mesmo ID de transação**.

## 11. Erros comuns
- **Esquecer de converter a resposta para JSON:** Chamar `response.json` sem o `await` ou acessar `response.body` esperando um objeto manipulável. O Playwright retorna Promises para métodos que leem o corpo da resposta.
- **Falta de Headers obrigatórios:** APIs de pagamento frequentemente bloqueiam requisições na porta de entrada (WAF/Cloudflare) se o `User-Agent` ou o `Content-Type` estiverem ausentes ou errados.
- **Confiar apenas no Status Code:** Retornar 200 não significa que o pagamento passou. Pode ser 200 com payload `{ status: "declined", reason: "insufficient_funds" }`. Sempre valide os campos internos!

## 12. Debugging
- Utilize `console.log(await response.text())` para ver exatamente o que o servidor devolveu, especialmente quando ocorre um Erro 500 ou o parsing do JSON falha (HTML de erro).
- Execute o Playwright com a flag de rastreamento de API ativada via variáveis de ambiente `DEBUG=pw:api`.
- Use o VS Code Debugger para colocar breakpoints logo após a linha do `request` e inspecionar o objeto `responseBody` na aba Variables.

## 13. Aplicação no projeto principal
No nosso framework, não faremos apenas requisições soltas. O `request` (APIRequestContext) será envelopado em **Services** (ex: `PaymentService`, `RefundService`). Entender a base de como o Playwright dispara o HTTP e lê a resposta é crucial, pois no projeto real você abstrairá isso. Por exemplo, criaremos uma função auxiliar que automaticamente injeta tokens JWT ou chaves de sandbox em todo request, reduzindo a duplicação de código vista nos exemplos desta fase.

## 14. Perguntas de entrevista
1. **P:** Qual a diferença entre usar o `request` (APIRequestContext) do Playwright em vez da biblioteca `axios` ou `fetch` nativo nos testes E2E?
   - *R:* O `APIRequestContext` compartilha o estado e cookies do contexto do navegador do Playwright (se derivado de um browser). Ele é rastreado nos relatórios do Playwright (HTML Report, Tracing), captura logs de rede automaticamente e possui integrações nativas e asserções otimizadas com o objeto `expect`.
2. **P:** Como você validaria, usando Playwright API, que o tempo de resposta de um endpoint de autorização de pagamento está abaixo do SLA de 1000ms?
   - *R:* O Playwright não expõe diretamente o tempo na response como algumas ferramentas de performance, mas podemos calcular usando `performance.now()` ou `Date.now()` antes e depois do `request.post()`, e então fazer um `expect(timeElapsed).toBeLessThan(1000)`.

## 15. Checklist
- [ ] Entendi como disparar GET e POST utilizando `request`.
- [ ] Sei como enviar Headers (incluindo autenticação).
- [ ] Sei extrair o corpo da resposta usando `await response.json()`.
- [ ] Consegui utilizar `expect` para validar códigos de status (ex: `.toBe(201)`).
- [ ] Consegui utilizar `expect` para checar campos específicos dentro do JSON de resposta.

## 16. Critério para avançar
Você está pronto para a próxima fase se conseguiu completar o Desafio (Nível 3) e compreende perfeitamente por que usar Headers (como Idempotency-Key) e como manipular os dados retornados no Playwright sem recorrer a bibliotecas de terceiros como `axios` ou `supertest`.
