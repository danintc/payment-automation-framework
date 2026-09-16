# Fase 7: PostgreSQL + SQL - Trilha de Banco de Dados

## 01. O que você vai aprender
- Entender a estrutura de um banco de dados relacional em sistemas de pagamento (esquemas, tabelas, relacionamentos).
- Escrever consultas SQL essenciais para validação de testes (SELECT, WHERE, JOIN, GROUP BY).
- Utilizar funções de agregação (SUM, COUNT) relevantes em contextos financeiros.
- Validar estados transacionais no banco para garantir que a API fez exatamente o que deveria.

## 02. Por que isso importa para um QA
Em sistemas de pagamento, o que a API retorna em um JSON (status 200, `"status": "PAID"`) é apenas a ponta do iceberg. A verdadeira fonte da verdade (*Source of Truth*) é o banco de dados. Um falso positivo na API pode esconder que um pagamento foi registrado com o valor errado no banco, que um webhook falhou ou que taxas de *gateway* não foram descontadas, causando prejuízos financeiros graves. Como SDET, você não valida apenas o endpoint: você cruza o retorno da API com o estado persistido no banco de dados para garantir integridade ponta a ponta.

## 03. Pré-requisitos
- Compreensão básica sobre o que é um banco de dados relacional.
- Conhecimento da arquitetura teórica do nosso sistema de pagamentos simulado.
- (Opcional, mas recomendado) Instalação de uma ferramenta cliente para conectar ao PostgreSQL, como DBeaver, pgAdmin ou DataGrip.

## 04. Conceitos
- **Tabela e Esquema (Schema):** Onde os dados moram. O esquema organiza logicamente as tabelas (ex: `pagamentos.transacoes`).
- **Chave Primária (PK) / Estrangeira (FK):** A PK identifica uma linha de forma única (ex: `transaction_id`). A FK cria o relacionamento com outras tabelas (ex: `user_id` apontando para a tabela de usuários).
- **CRUD (SQL):** INSERT (Criar), SELECT (Ler), UPDATE (Atualizar), DELETE (Deletar). Nosso foco como QA será massivamente no **SELECT**.
- **JOINs:** Como unir informações de várias tabelas. Em pagamentos, frequentemente juntamos a tabela de `transactions` com `users` ou `payment_methods`.
- **Agregações:** Funções matemáticas no SQL como `SUM(amount)` para verificar, por exemplo, o saldo total gerado por transações de um lojista específico.

## 05. Explicação mastigada
Imagine o banco de dados como uma planilha Excel gigantesca e blindada, onde cada aba é uma "tabela". 
Se você testa uma API que processa a cobrança de um Pix de R$ 50,00, a API pode responder "Sucesso". Mas será que o banco salvou exatamente R$ 50,00? E se salvou R$ 5,00 por um erro clássico de conversão de centavos no backend?
O SQL é a linguagem que nos permite perguntar a essa "planilha" exatamente o que aconteceu e validar a verdade. 
- Com o `SELECT`, escolhemos quais colunas ver (`amount`, `status`). 
- Com o `WHERE`, filtramos pelo pagamento específico recém-criado no teste (ex: `transaction_id = 'tx_123'`).
- Com o `JOIN`, podemos enriquecer a pergunta: "Me traga os dados do pagamento e também o email do cliente que pagou para garantir que foi creditado para a pessoa certa".

## 06. Exemplos
**Cenário de Teste:** Criar uma cobrança Pix via API e verificar se o status inicial inserido no banco é `PENDING`.

**Tabela: `transactions`**
| id | user_id | amount | payment_method | status | created_at |

Consulta SQL de validação:
```sql
SELECT status, amount 
FROM transactions 
WHERE id = 'pix_98765';
```
*Resultado Esperado no banco:* `status = 'PENDING'`, `amount = 5000` (pagamentos geralmente salvam valores em *cents*, ou seja, 50,00 * 100).

**Cenário de Fechamento de Fatura:** Somar todas as transações pagas de um usuário no dia atual.
```sql
SELECT user_id, SUM(amount) as total_paid
FROM transactions
WHERE status = 'PAID' AND user_id = 'user_123'
GROUP BY user_id;
```

## 07. Código comentado

Abaixo, um exemplo de query SQL complexa focada em QA. Embora depois venhamos a chamar isso no Playwright via TypeScript, aqui focamos puramente no script SQL que fará a validação de negócio:

```sql
-- Busca uma transação específica para validar sua integridade após a chamada da API
SELECT 
    t.id AS transaction_id,
    t.amount,
    t.status,
    u.email AS customer_email
FROM transactions t
-- O JOIN liga a transação ao usuário correspondente usando as chaves (FK e PK)
INNER JOIN users u ON t.user_id = u.id
-- Filtramos pelo ID da transação que a API nos devolveu no Response Body no teste
WHERE t.id = 'tx_12345ABC'
  -- É uma ótima prática de QA verificar também o lojista (merchant)
  -- para evitar falhas graves de vazamento ou cruzamento de dados (data leak/tenant leak)
  AND t.merchant_id = 'merch_001';
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Encontrar o status de uma transação de cartão de crédito que você acabou de criar via API de testes, sabendo apenas o ID do cliente.

**Passo a passo:**
1. Abra seu cliente SQL e conecte-se ao banco de dados do ambiente de testes (`QA_DB`).
2. Escreva o `SELECT` básico para trazer as colunas relevantes:
   ```sql
   SELECT id, status, amount FROM transactions;
   ```
3. Adicione a condição `WHERE` para filtrar as compras daquele usuário específico (o usuário *mockado* que seu teste usou):
   ```sql
   SELECT id, status, amount 
   FROM transactions 
   WHERE user_id = 'usr_999';
   ```
4. Como podem existir várias transações para esse cliente, ordene pela mais recente e pegue só a primeira (`LIMIT 1`):
   ```sql
   SELECT id, status, amount 
   FROM transactions 
   WHERE user_id = 'usr_999'
   ORDER BY created_at DESC 
   LIMIT 1;
   ```
5. Execute e valide se o retorno (`status`) condiz com o esperado após a chamada da sua API.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Validar uma operação de Estorno (Refund) persistida no banco.
1. Considere que seu teste acabou de chamar a API de `POST /refunds` para a transação `tx_888`.
2. Escreva uma query SQL para verificar:
   - Se a transação original na tabela `transactions` (`id = 'tx_888'`) teve seu status atualizado para `REFUNDED`.
   - Se uma nova linha de histórico foi inserida corretamente na tabela `refunds` com `transaction_id = 'tx_888'` contendo o valor exato devolvido.

**Dica:** Você pode fazer isso com dois `SELECT` separados ou tentar um `JOIN` entre as tabelas `transactions` e `refunds`.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Auditoria de Saldo (Reconciliation).
Em sistemas financeiros robustos, o saldo de um lojista na tabela de carteiras (`wallets.balance`) deve ser **exatamente** igual à soma de todas as transações com status `PAID`, subtraindo as transferências de saque (`withdrawals`).
Escreva uma query SQL avançada que:
1. Agrupe e calcule o somatório das transações `PAID` para o `merchant_id = 'loja_555'` da tabela `transactions`.
2. Agrupe e calcule o somatório de `withdrawals` realizados pelo mesmo `merchant_id`.
3. Compare o saldo calculado dinamicamente com o saldo armazenado na coluna `balance` da tabela `wallets`, indicando se existe ou não uma diferença (furo de caixa).

*(Dica avançada: Explore o uso de CTEs - comandos `WITH` - para organizar as somatórias parciais antes de realizar a junção e o cálculo final).*

## 11. Erros comuns
- **Esquecer de conferir o ambiente:** Você roda a query de validação no banco de `dev` e não entende por que não acha a transação que a automação disparou em `qa`. Sempre valide a string de conexão.
- **Diferenças de Tipagem:** Tentar comparar uma string com um UUID de forma estrita, ou esquecer da regra de centavos (*cents*). A API respondeu `50.00`, o banco salvou `5000` (inteiro). O QA falha o teste injustamente.
- **Falta de `LIMIT 1` ou ordenação incorreta:** Ao buscar pela transação mais recente sem o ID exato, se esquecer do `ORDER BY created_at DESC LIMIT 1`, a consulta retornará a primeira transação antiga inserida no banco, gerando um Falso Positivo brutal.

## 12. Debugging
- **Query travando a automação (Timeout)?** Se seu `SELECT` for ruim e fizer *full table scan*, o Playwright vai dar timeout de espera. Como QA, pesquise as chaves (PKs) nos filtros e use índices quando aplicável.
- **Nenhum resultado voltando com JOIN?** Revise se você utilizou `INNER JOIN` mas uma das partes do relacionamento não existe (por exemplo, buscando estornos de um pagamento não estornado). Nesses casos, um `LEFT JOIN` é mais amigável para debug porque a linha da tabela principal vai continuar aparecendo (com os campos atrelados em `NULL`).
- **Valores nulos?** Use `IS NULL` no SQL (`WHERE status IS NULL`). Fazer a query `WHERE status = NULL` nunca retorna nada, pois a comparação com nulo é, por definição no SQL, indefinida.

## 13. Aplicação no projeto principal
Em projetos de automação robustos não utilizamos uma interface visual em meio à execução. Na próxima fase da trilha, usaremos a biblioteca Node `pg` (node-postgres) em conjunto com o Playwright. Vamos encapsular as queries poderosas que aprendemos aqui em funções dentro de um arquivo Helper (`dbHelper.ts`). Elas buscarão o estado do Postgres em milissegundos e usaremos as *assertions* do Playwright (`expect(dbResult.amount).toBe(5000)`) para validar a coerência transacional pós API call.

## 14. Perguntas de entrevista
1. **P:** Por que devemos validar o banco de dados em testes de API e não apenas confiar no *status code* 200 retornado?
   **R:** Porque a API pode falhar silenciosamente ou mascarar um erro de gravação (*silent failure*). Ela retorna sucesso, mas perdeu a comunicação com a base ou salvou valores distorcidos. Em sistemas de pagamento, garantir que a persistência (valores exatos, status final, FKs e conciliação) ocorreu perfeitamente é absolutamente crítico e inegociável.
2. **P:** Qual a diferença entre `INNER JOIN` e `LEFT JOIN` sob a ótica da automação de testes?
   **R:** O `INNER JOIN` é restritivo e traz apenas quando o dado existe em ambas as tabelas (ideal para checar integridade obrigatória). Já o `LEFT JOIN` é incrível para garantir que algo *não* foi criado. Ex: garantir que um estorno não ocorreu para a `transacao_id = X` checando se o retorno do lado direito é nulo.
3. **P:** Como você testaria se a soma total diária das vendas reflete corretamente o saldo de um cliente via SQL?
   **R:** Utilizo a função agregadora `SUM(amount)`, aliada à cláusula `GROUP BY user_id` na tabela de transações. Filtro exclusivamente pelos `status = 'PAID'` e por uma data específica. Em seguida, comparo esse valor consolidado com o total esperado na tabela de fechamentos/faturas para identificar falhas financeiras (*financial drift*).

## 15. Checklist
- [ ] Compreendi a função das operações CRUD, focando na leitura de validação (`SELECT`).
- [ ] Sei escrever e analisar consultas básicas com `SELECT`, `WHERE`, `ORDER BY` e `LIMIT 1`.
- [ ] Entendo como usar `INNER JOIN` para relacionar transações financeiras e contas/usuários.
- [ ] Consigo utilizar `SUM()` e `GROUP BY` para auditar somatórios e bater caixas virtualmente.
- [ ] Entendo de forma clara o conceito de salvar valores monetários sempre como centavos (inteiros) no PostgreSQL.

## 16. Critério para avançar
Você deve conseguir abrir sua interface de banco de dados (SQL client) e escrever, do zero e sem consultar documentação, uma query funcional que retorne a soma de todas as transações marcadas como `PAID` pertencentes a um determinado `user_id`. Uma vez que esse conceito esteja fixado na mente, você está liberado para automatizar isso integrando o TypeScript no Playwright.
