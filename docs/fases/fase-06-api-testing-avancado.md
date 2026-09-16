# Fase 6: API Testing Avançado

## 01. O que você vai aprender
- Como lidar com cenários multi-step (fluxos complexos de pagamento).
- Criação de payloads dinâmicos com geradores de dados (Faker).
- Gerenciamento de estado entre diferentes chamadas de API.
- Estratégias eficientes de setup e teardown (limpeza de dados de teste).
- Como isolar testes utilizando dados únicos para rodar testes em paralelo sem conflitos.

## 02. Por que isso importa para um QA
Em sistemas de pagamento, as transações quase nunca são eventos isolados. Um pagamento envolve a criação do cliente, a geração de um pedido, a autorização no gateway, a captura, a emissão da nota fiscal e os webhooks de notificação. Testar apenas um endpoint isolado (como um `POST /pagamento`) é insuficiente e mascara bugs de integração. Como QA e SDET, dominar cenários de múltiplos passos, gerar massa de dados dinâmica que evita colisões (como CPFs e e-mails duplicados) e garantir a limpeza da base (teardown) são habilidades que diferenciam um testador júnior de um engenheiro de qualidade sênior capaz de construir pipelines de testes resilientes e não-flaky.

## 03. Pré-requisitos
- Compreensão sólida dos verbos HTTP e códigos de status (Fases anteriores).
- Experiência básica com o `APIRequestContext` do Playwright (Fases anteriores).
- Conhecimento em TypeScript, Promises e `async/await`.
- Familiaridade com a estrutura do Playwright Test (hooks como `beforeEach`, `afterEach`, `afterAll`).

## 04. Conceitos
- **Cenários Multi-step:** Testes que requerem uma sequência de chamadas de API onde a saída de uma chamada é a entrada da próxima. (Ex: Auth -> Criar Cliente -> Criar Cobrança).
- **Geração de Dados Dinâmicos (Data Faker):** Uso de bibliotecas como o `@faker-js/faker` para gerar dados únicos (e-mails, nomes, UUIDs, cartões de crédito falsos) em tempo de execução.
- **Gerenciamento de Estado:** Armazenamento temporário de IDs de transações, tokens ou status em variáveis durante a execução de um teste para validações e limpeza.
- **Teardown (Limpeza de Dados):** O processo de deletar, estornar ou inativar as entidades criadas pelo teste, deixando o banco de dados limpo para execuções futuras.

## 05. Explicação mastigada
Imagine que você precisa testar um fluxo de compra com Pix. O que parece ser um simples botão "Pagar" envolve uma dança entre vários endpoints:
1. Você se autentica e pega um `Bearer Token`.
2. Você cria um cliente na API passando um CPF (que precisa ser válido e único).
3. Você cria a intenção de pagamento (Order) passando o ID do cliente.
4. A API retorna o copia-e-cola (payload do Pix).
5. Você precisa simular o pagamento (talvez num endpoint de mock ou webhook).
6. Você verifica se o status do pedido mudou para "PAGO".

Se você chumbar (hardcode) o mesmo CPF no código, o segundo teste que rodar vai falhar com "CPF já cadastrado". Se você não guardar os IDs, não vai conseguir cancelar o pedido depois, sujando o banco de dados.

Para resolver isso:
- Usamos **Faker** para garantir que cada teste tenha um usuário novinho em folha.
- Guardamos os **IDs criados em arrays ou variáveis** dentro do próprio arquivo de teste.
- Usamos o bloco **`test.afterAll` ou `test.afterEach`** do Playwright para iterar sobre esses IDs e chamar endpoints de deleção (ex: `DELETE /clientes/{id}`), garantindo que o banco de dados não vire um lixão.

## 06. Exemplos

### Exemplo de fluxo dependente (Multi-step)
Em sistemas financeiros, muitas vezes você não pode apagar um registro diretamente, você deve "cancelar" ou "estornar" a transação. O gerenciamento do estado dos IDs criados permite fazer isso no `afterEach`.

```typescript
// Gerando um e-mail aleatório para não dar conflito
const email = faker.internet.email();

// Passo 1: Criar cliente
const customerRes = await request.post('/api/v1/customers', { data: { email } });
const customerId = (await customerRes.json()).id;

// Passo 2: Criar transação para esse cliente
const txRes = await request.post('/api/v1/transactions', { 
  data: { customerId, amount: 5000 } 
});
const txId = (await txRes.json()).id;

// O teste valida a transação, e depois o txId é usado na limpeza para fazer o refund ou inativação.
```

## 07. Código comentado

Aqui temos um código completo de teste demonstrando dados dinâmicos, fluxo multi-step e limpeza.

```typescript
import { test, expect } from '@playwright/test';
import { faker } from '@faker-js/faker';

test.describe('Fluxo Completo de Pagamento Pix', () => {
  // Estado para armazenar os IDs das entidades criadas durante o teste
  // Isso é crucial para limparmos a sujeira depois
  let createdCustomers: string[] = [];
  let createdOrders: string[] = [];

  // Teardown: Limpando a sujeira independentemente de o teste passar ou falhar
  test.afterEach(async ({ request }) => {
    console.log('Iniciando teardown...');
    
    // Deletar orders criadas (ou estornar) primeiro (por causa das Foreign Keys)
    for (const orderId of createdOrders) {
      const res = await request.delete(`/api/v1/orders/${orderId}`);
      if (!res.ok()) console.error(`Falha ao limpar order ${orderId}`);
    }
    
    // Deletar clientes
    for (const customerId of createdCustomers) {
      const res = await request.delete(`/api/v1/customers/${customerId}`);
      if (!res.ok()) console.error(`Falha ao limpar customer ${customerId}`);
    }

    // Resetamos os arrays para o próximo teste
    createdOrders = [];
    createdCustomers = [];
  });

  test('Deve criar cliente, gerar cobrança Pix e simular pagamento com sucesso', async ({ request }) => {
    // 1. Dados Dinâmicos usando Faker para evitar "Duplicate Entry" no banco
    const payloadCliente = {
      name: faker.person.fullName(),
      email: faker.internet.email(),
      document: faker.string.numeric(11) // Simulando um CPF
    };

    // 2. Passo 1: Criar Cliente
    const customerResponse = await request.post('/api/v1/customers', {
      data: payloadCliente
    });
    expect(customerResponse.ok()).toBeTruthy();
    
    const customerData = await customerResponse.json();
    const customerId = customerData.id;
    // Guardamos o ID no nosso estado de teste para o Teardown!
    createdCustomers.push(customerId);

    // 3. Passo 2: Criar Cobrança (Order) vinculada ao cliente
    const payloadOrder = {
      customerId: customerId,
      amount: 15000, // R$ 150,00 em centavos
      paymentMethod: 'PIX'
    };

    const orderResponse = await request.post('/api/v1/orders', {
      data: payloadOrder
    });
    expect(orderResponse.status()).toBe(201);
    
    const orderData = await orderResponse.json();
    const orderId = orderData.id;
    const pixCopyPaste = orderData.pix.copyAndPaste;
    
    // Guardamos a order para limpar depois
    createdOrders.push(orderId);

    // 4. Passo 3: Simular pagamento do Pix (Mock de Webhook)
    // Em ambientes de homologação, gateways oferecem endpoints para simular o pagamento.
    const mockPaymentResponse = await request.post(`/api/v1/mock/pix/pay`, {
      data: { copyAndPaste: pixCopyPaste }
    });
    expect(mockPaymentResponse.ok()).toBeTruthy();

    // 5. Passo 4: Validar se o status do pedido atualizou
    const fetchOrderResponse = await request.get(`/api/v1/orders/${orderId}`);
    const fetchOrderData = await fetchOrderResponse.json();
    expect(fetchOrderData.status).toBe('PAID');
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
Vamos criar um teste que cadastra um cartão de crédito (Tokenização) para um cliente dinâmico e depois deleta o cartão e o cliente.

**Passo a passo:**
1. Crie um arquivo `specs/cartao.spec.ts`.
2. Importe o `test`, `expect` e o `@faker-js/faker`.
3. Crie um `test.describe` e inicie dois arrays: `let cartoesCriados: string[] = [];` e `let clientesCriados: string[] = [];`.
4. Faça um `test.afterEach` onde você faz um loop sobre `cartoesCriados` e faz um `DELETE /api/v1/cards/{id}`, e depois repete o processo para deletar `clientesCriados`.
5. No seu `test`, crie um cliente via API usando `faker` e adicione o ID no array de clientes.
6. Faça um POST para `/api/v1/cards` passando o ID do cliente e os dados de um cartão falso (você pode usar `faker.finance.creditCardNumber()`).
7. Faça uma asserção de que o status é 201 e adicione o ID do cartão ao array `cartoesCriados`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
Implemente um teste de **Estorno parcial de pagamento**.
- **Objetivo:** O teste deve criar uma transação com cartão de crédito de R$ 100,00, depois realizar um refund (estorno) de R$ 30,00, e validar que o saldo final cobrado do cliente no sistema é R$ 70,00.
- **Requisitos:**
  - Crie dinamicamente cliente e cartão.
  - Gere a transação passando o cliente e o cartão.
  - Chame o endpoint `POST /api/v1/transactions/{id}/refund`.
  - Verifique os valores retornados com `GET /api/v1/transactions/{id}` (o valor final ou refund list deve bater com a matemática).
  - Garanta que no `afterEach` o cliente e o cartão sejam removidos ou inativados.

## 10. Desafio (Nível 3 - Challenge)
**Webhooks em cenários multi-step (Polling).**
Em sistemas de pagamento, as confirmações de transação geralmente acontecem de forma assíncrona. O pagamento é feito, mas o sistema notifica o seu e-commerce através de um Webhook tempos depois.
**Desafio:** Crie um teste completo onde você simula a criação de um pedido, dispara uma notificação (simulando que o gateway mandou o webhook para o seu endpoint: `POST /webhooks/gateway`) informando que o pagamento foi autorizado. Após disparar o webhook, implemente um loop de *polling* (fazendo requisições GET periódicas) na sua API de pedidos com `expect.poll()` do Playwright, até garantir que o status da transação mudou para `APPROVED`. O teste deve suportar esperar até 10 segundos sem falhar prematuramente.

## 11. Erros comuns
- **Esquecer de limpar os dados (No Teardown):** Acumula lixo no banco de dados, o que em poucas semanas faz os testes de performance ficarem lentos e causa colisões de restrições de banco (Unique Constraints).
- **Hardcoding Data:** Colocar `email: "teste@teste.com"`. O primeiro teste passa, o segundo (ou outro trabalhador paralelo) quebra com `409 Conflict`.
- **Condições de Corrida na Limpeza (FK constraints):** Usar `test.afterEach` e não garantir a ordem de exclusão. Se uma `Order` tem chave estrangeira pro `Customer`, você não pode deletar o `Customer` antes de deletar a `Order`.
- **Não tratar falhas no Teardown:** Se o teardown jogar um erro e parar a execução, outros testes podem não conseguir limpar o banco. Recomenda-se ignorar asserções duras de erro na limpeza.

## 12. Debugging
- **Trace de IDs perdidos:** Se seu teardown não estiver funcionando, imprima no console (`console.log`) os arrays de IDs logo antes do loop no `afterEach` para verificar se os testes estão populando o array corretamente.
- **Inspecionar chamadas encadeadas:** Ao usar o *Playwright UI Mode*, clique em cada requisição de rede gerada no teste para ver como o Token, ID ou Payload estão sendo passados de um passo para o outro.

## 13. Aplicação no projeto principal
No nosso simulador de gateway de pagamentos, aplicaremos esses conceitos criando suítes de testes de regressão (E2E API) focadas em fluxos completos de e-commerce. Todo teste de pagamento, assinatura ou estorno possuirá uma estratégia robusta de limpeza de base de dados e usaremos o Faker para assegurar que podemos rodar o projeto em *Workers* em paralelo sem que um teste afete a massa de dados do outro.

## 14. Perguntas de entrevista
1. **Pergunta:** Como você garante que testes que rodam em paralelo não manipulem ou corrompam a mesma massa de dados na API?
   *Resposta Esperada:* Abordo a técnica de criação de dados dinâmicos com geradores (ex: Faker) e instanciando clientes e usuários novos dentro do contexto local de cada teste. Em seguida, utilizo mecanismos de teardown para limpar os dados inseridos logo após a execução daquele cenário.
2. **Pergunta:** Explique como testar um endpoint de pagamento onde o status é atualizado de forma assíncrona após alguns segundos.
   *Resposta Esperada:* Utilizaria técnicas de *polling* dentro do teste Playwright. Criaria um bloco `expect.poll` que faria chamadas GET periódicas para o endpoint de status da transação até receber a resposta esperada ou atingir um timeout predefinido.
3. **Pergunta:** Você encontrou um cenário onde é impossível deletar um usuário criado pela API para testes devido a regras fiscais (compliance). O que fazer?
   *Resposta Esperada:* Como SDET, se o *hard delete* (DELETE HTTP) não for possível, oriento o desenvolvimento a oferecer um mecanismo de inativação (soft delete) nos ambientes de teste. O setup dos testes continuaria a gerar usuários dinâmicos e, ao invés de apagá-los, executaríamos um script ou API de desativação para não sujar as métricas do negócio.

## 15. Checklist
- [ ] Compreendi a importância de testes multi-step no contexto financeiro.
- [ ] Adicionei a biblioteca `@faker-js/faker` no projeto (`npm install -D @faker-js/faker`).
- [ ] Implementei arrays de estado (ex: `ordersIds`) para guardar referências.
- [ ] Implementei rotinas de `test.afterEach` ou `test.afterAll` para limpeza seguindo a ordem correta de deleção.
- [ ] Construí fluxos encadeando requisições, onde a saída de uma API é usada como entrada da próxima.

## 16. Critério para avançar
Você está pronto para avançar quando tiver construído com sucesso pelo menos dois cenários multi-step (Ex: Cliente -> Cobrança -> Pagamento), o arquivo de teste rodar repetidas vezes localmente em paralelo sem gerar o erro de "Registro já existente", e o banco de dados/API estiver sem resíduos após a execução da suíte, sinalizando que seu teardown foi impecável.
