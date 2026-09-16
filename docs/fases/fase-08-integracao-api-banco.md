# Fase 8: Integração API + Banco

## 01. O que você vai aprender
Nesta fase, você aprenderá a conectar sua suíte de testes do Playwright a um banco de dados relacional (PostgreSQL). Vamos abordar como configurar a biblioteca `pg`, criar *fixtures* customizadas para injetar o *pool* de conexões de banco de dados diretamente nos seus testes, e, o mais importante, como validar que as respostas da API refletem fielmente o estado real dos dados no banco.

## 02. Por que isso importa para um QA
APIs podem mentir. Em sistemas de pagamento, uma API pode retornar um HTTP 200 OK informando que um Pix foi processado, mas por uma falha de concorrência ou um erro não tratado no backend, o saldo da carteira (wallet) do lojista não foi atualizado no banco de dados. 
Como SDET, você sabe que o banco de dados é a **fonte da verdade**. Validar o banco de dados permite:
1. Garantir a integridade financeira (o dinheiro não sumiu no ciberespaço).
2. Criar pré-condições de teste (massa de dados) de forma incrivelmente rápida via `INSERT`s, sem depender de múltiplas chamadas de API lentas.
3. Validar processamentos assíncronos (ex: mensageria/filas) onde a API apenas devolve um *202 Accepted* e o processamento real ocorre em background.

## 03. Pré-requisitos
- Node.js e TypeScript configurados.
- Playwright Test instalado.
- Acesso a um banco de dados PostgreSQL (local via Docker ou nuvem).
- Entendimento sólido de Playwright Fixtures (visto nas fases anteriores).
- Instalação dos pacotes do Postgres: `npm install pg` e `npm install -D @types/pg`.

## 04. Conceitos
- **Connection Pool (Pool de Conexões)**: É um cache de conexões de banco de dados mantido em memória. Em vez de abrir e fechar uma conexão a cada query (o que é custoso e lento), o *Pool* reaproveita conexões existentes, tornando seus testes muito mais rápidos.
- **Fixture de Banco**: Um mecanismo do Playwright onde injetamos nosso *Pool* ou um objeto *DatabaseClient* direto no teste, garantindo que a conexão está pronta para uso no início do teste e será devidamente encerrada (teardown) no final.
- **State Validation (Validação de Estado)**: A prática de comparar o *Output* de um sistema (a resposta HTTP) com o seu *State* (o registro salvo no banco de dados).

## 05. Explicação mastigada
Imagine que você está testando uma API de Checkout. O cliente passa o cartão de crédito e a API responde: `"status": "APPROVED"`. 
Para um teste superficial, afirmar que o status é "APPROVED" basta. Mas num sistema de pagamentos de verdade, você precisa abrir o banco de dados e perguntar: 
*"Ei tabela de `transactions`, a transação ID 1234 realmente está com status 'APPROVED'? E a tabela de `wallets`, o saldo do lojista aumentou de R$ 100 para R$ 150?"*
Para fazer isso, nós configuramos o `pg` (a ponte entre o Node e o Postgres), criamos uma chavinha (fixture) chamada `db` no Playwright, e dentro do nosso `test()`, fazemos requisições SQL direto nas nossas asserções (`expect`).

## 06. Exemplos

**Exemplo básico de Query no Postgres via Node:**
```typescript
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: 'postgresql://postgres:senha@localhost:5432/payment_db'
});

const result = await pool.query('SELECT status FROM transactions WHERE id = $1', ['txn_123']);
console.log(result.rows[0].status); // 'COMPLETED'
```

## 07. Código comentado

Vamos criar uma arquitetura limpa usando **Fixtures** para não poluir os testes.

**1. Configurando a Fixture (fixtures.ts)**
```typescript
import { test as base } from '@playwright/test';
import { Pool } from 'pg';

// Definimos o tipo da nossa fixture
type MyFixtures = {
  db: Pool;
};

// Estendemos o teste base do Playwright
export const test = base.extend<MyFixtures>({
  db: async ({}, use) => {
    // SETUP: Roda antes do teste
    const pool = new Pool({
      connectionString: process.env.DATABASE_URL || 'postgresql://admin:admin@localhost:5432/paydb',
    });
    
    // Injeta o pool no teste
    await use(pool);
    
    // TEARDOWN: Roda depois do teste (mesmo se falhar)
    await pool.end();
  },
});

export { expect } from '@playwright/test';
```

**2. O Teste (pix-payment.spec.ts)**
```typescript
import { test, expect } from './fixtures'; // Importamos o nosso test customizado!

test('Deve processar um Pix e atualizar o banco de dados corretamente', async ({ request, db }) => {
  const payload = {
    amount: 5000, // R$ 50,00
    method: 'PIX',
    receiverId: 'merch_789'
  };

  // 1. Fazemos a chamada na API
  const response = await request.post('/api/v1/payments', { data: payload });
  expect(response.status()).toBe(201);
  
  const responseBody = await response.json();
  const transactionId = responseBody.id;

  // 2. Consultamos o Banco de Dados para validar a fonte da verdade
  const { rows } = await db.query(
    'SELECT status, amount FROM transactions WHERE id = $1', 
    [transactionId]
  );

  // 3. Asserções combinadas (API x Banco)
  expect(rows.length).toBe(1); // Garante que o registro foi criado
  expect(rows[0].status).toBe('COMPLETED'); // Valida o estado real
  expect(rows[0].amount).toBe(5000); // Valida integridade do valor
});
```

## 08. Exercício guiado (Nível 1 - Guided)

**Objetivo:** Validar o saldo de uma carteira após um depósito.

1. Instale as dependências: `npm i pg` e `npm i -D @types/pg`.
2. Configure sua fixture de `db` exatamente como no passo 07.
3. Crie um arquivo `wallet.spec.ts`.
4. No teste, chame `GET /api/v1/wallets/user_123` e guarde o saldo atual.
5. Chame `POST /api/v1/deposits` com `{ userId: "user_123", amount: 1000 }`.
6. Use o `db.query('SELECT balance FROM wallets WHERE user_id = $1', ['user_123'])`.
7. Faça um `expect` validando que o saldo retornado pelo banco de dados é igual ao saldo anterior + 1000.

## 09. Exercício sozinho (Nível 2 - Semi-guided)

**Objetivo:** Validar um fluxo de Reembolso (Refund) de Cartão de Crédito.

- Rota: `POST /api/v1/refunds`
- Payload: `{ "transactionId": "txn_999" }`
- **Requisitos do Teste:**
  1. Identifique uma transação paga no banco (faça um `INSERT` prévio se necessário).
  2. Solicite o reembolso via API.
  3. Valide no banco de dados que:
     - O `status` da transação original em `transactions` mudou de `PAID` para `REFUNDED`.
     - Um novo registro foi criado na tabela `refunds` referenciando a `transaction_id`.

## 10. Desafio (Nível 3 - Challenge)

**Objetivo:** Automação total de Massa de Dados via Banco na Fixture.

Crie uma nova fixture chamada `testUser`. Essa fixture deve, no seu bloco de setup:
1. Gerar um usuário aleatório com um UUID (usando o `db`).
2. Inserir esse usuário na tabela `users`.
3. Inserir uma carteira na tabela `wallets` com R$ 100 de saldo para este usuário.
4. Passar os dados desse usuário (`{ id, email, walletId }`) para o teste (via `use()`).
5. No bloco de teardown da fixture, fazer um `DELETE` desse usuário e de sua carteira, limpando a sujeira e deixando o banco impecável, não importando se o teste passou ou falhou.

## 11. Erros comuns
- **Esquecer de fechar o Pool:** Se você não der `await pool.end()` (ou `client.release()`), a thread do Node vai ficar pendurada eternamente no fim dos testes, causando *timeouts* na pipeline.
- **SQL Injection em Testes:** Usar concatenação de strings `SELECT * FROM users WHERE id = '${id}'` em vez de queries parametrizadas (`WHERE id = $1`). Mesmo em testes, habitue-se às melhores práticas de segurança.
- **Condições de Corrida (Race Conditions):** A API retorna 202 Accepted para um pagamento assíncrono. O teste imediatamente bate no banco e verifica o status, mas ainda está `PENDING` porque o *worker* não terminou. Em cenários assíncronos, você precisará de uma função de *polling* (ex: `expect.poll`) no banco de dados, em vez de uma query direta e única.

## 12. Debugging
- **"O teste trava e não termina"**: Verifique se todas as conexões estão sendo fechadas no final das fixtures.
- **Erro de Conexão (ECONNREFUSED)**: Verifique se sua variável `DATABASE_URL` está correta e se o container Docker do Postgres está rodando (`docker ps`).
- **Ver os dados que voltaram**: Use `console.log(JSON.stringify(rows, null, 2))` depois de um `db.query` para entender exatamente o formato dos dados e tipos que o Postgres está retornando (ex: decimais no Postgres muitas vezes voltam como *strings* no Node).

## 13. Aplicação no projeto principal
No nosso **Payment Gateway**, o banco de dados é vital. Nós usaremos esta integração para:
- Validar se os **Webhooks** enviados pelos parceiros estão sendo gravados no nosso banco como eventos processados.
- Preparar o banco criando chaves Pix (`pix_keys`) fictícias em frações de segundo para os testes de transferência.
- Validar as tabelas de *Ledger* (livro-razão) para garantir que uma operação de crédito e débito resultou numa soma zero, garantindo consistência contábil dupla.

## 14. Perguntas de entrevista
1. **"Por que testar o banco de dados se a API já retorna o status da operação?"**
   *Resposta:* A API é apenas uma camada de apresentação de dados. O backend pode ter *bugs* de cache, pode falhar silenciosamente ao comitar uma transação no banco, ou disparar falsos positivos. O banco de dados representa o estado real e financeiro absoluto do sistema.
2. **"Como você gerencia o setup de dados para testes paralelos sem que um teste interfira no outro?"**
   *Resposta:* Eu crio fixtures que inserem entidades isoladas (ex: um ID de lojista único por teste) direto via SQL. Ao final, a própria fixture faz o teardown. Dessa forma, posso rodar 50 testes em paralelo e eles nunca colidirão no banco.

## 15. Checklist
- [ ] Pacotes `pg` e `@types/pg` estão instalados.
- [ ] String de conexão de banco isolada no arquivo `.env`.
- [ ] Fixture do Playwright criada gerenciando o ciclo de vida do `Pool`.
- [ ] Queries parametrizadas (`$1, $2`) usadas para evitar *syntax errors* e segurança.
- [ ] Assertivas combinando `expect` de propriedades da API com colunas do Banco.

## 16. Critério para avançar
Para dar esta fase como concluída, você deve ter um script de teste onde uma requisição de pagamento é feita via Playwright `request`, uma consulta é realizada via `db.query()`, e há pelo menos um `expect` validando as duas coisas juntas. Se a suite de testes iniciar, executar e encerrar (sem travar o terminal), você domina a integração banco-API.
