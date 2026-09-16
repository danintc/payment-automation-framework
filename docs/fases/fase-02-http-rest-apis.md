# Fase 2: HTTP + REST + APIs

## 01. O que você vai aprender
- A anatomia de uma requisição HTTP e como as APIs REST funcionam no mundo real.
- Como manipular e entender os métodos HTTP (GET, POST, PUT, PATCH, DELETE) em um contexto de pagamentos.
- O significado dos HTTP Status Codes mais cruciais para sistemas financeiros (200, 201, 400, 401, 403, 404, 409, 422, 500, 503).
- A importância dos Headers HTTP (Autenticação, Content-Type, Idempotency-Key).
- Como realizar chamadas HTTP diretas usando o `request` context do Playwright com TypeScript.

## 02. Por que isso importa para um QA
Em sistemas de pagamento, uma falha na comunicação da API não significa apenas uma tela em branco; significa que uma transação de milhares de reais pode ter sido processada em duplicidade, ou pior, aprovada sem fundos. 

Como QA, entender HTTP profundamente permite que você:
- **Antecipe cenários de erro:** Ao testar um POST para gerar um Pix, você não testará apenas o caminho feliz (201 Created), mas também o que acontece se enviar dados inválidos (422) ou tentar pagar algo que já foi pago (409 Conflict).
- **Entenda a segurança básica:** Você saberá a importância dos cabeçalhos como `Authorization` e `x-api-key` para garantir que apenas sistemas autorizados criem transações.
- **Valide a consistência:** Em pagamentos, não basta a API retornar "sucesso", é essencial validar se a idempotência funcionou e se os headers retornados estão corretos.

## 03. Pré-requisitos
- Compreensão básica sobre o que é uma API (abordado na Fase 1).
- Ambiente Playwright + TypeScript configurado.
- Noções básicas da sintaxe TypeScript (variáveis, async/await, interfaces).

## 04. Conceitos
- **HTTP (Hypertext Transfer Protocol):** O protocolo base da web. Funciona num modelo Cliente-Servidor (Playwright é o cliente, o Gateway de Pagamento é o servidor).
- **REST (Representational State Transfer):** Um conjunto de regras arquiteturais. APIs RESTful usam recursos (ex: `/transactions`, `/refunds`) e verbos HTTP.
- **Métodos HTTP:** 
  - `POST`: Criar algo novo (Ex: Criar um pagamento).
  - `GET`: Buscar algo (Ex: Consultar o status de um Pix).
  - `PUT`: Substituir um recurso inteiro (Ex: Atualizar todos os dados do lojista).
  - `PATCH`: Atualizar parcialmente (Ex: Mudar o status de uma transação para "CANCELED").
  - `DELETE`: Remover (Ex: Deletar um cartão salvo).
- **Status Codes de Pagamento:**
  - `2xx`: Sucesso. (201 Created para um novo Pix).
  - `4xx`: Erro do cliente. (400 Bad Request, 401 Unauthorized, 403 Forbidden, 409 Conflict se houver pagamento duplicado, 422 Unprocessable Entity para saldo insuficiente ou cartão recusado).
  - `5xx`: Erro do servidor. (500 Internal Server Error, 503 Service Unavailable se o banco central caiu).
- **Headers:** Metadados da requisição. Importantes em pagamentos: `Authorization`, `Idempotency-Key` (evitar cobrança dupla em caso de retry), `Content-Type: application/json`.

## 05. Explicação mastigada
Imagine o HTTP como o serviço de correios, e a API REST como a agência.
1. O **Método (Verbo)** é o que você quer fazer na agência. (POST = Enviar um pacote, GET = Rastrear um pacote).
2. O **Endpoint (URI)** é o endereço do destino do pacote. (`/v1/payments`).
3. O **Header (Cabeçalho)** é o selo de autenticação, o carimbo de urgência, ou a etiqueta dizendo "Isso é uma caixa de sapatos" (`Content-Type`).
4. O **Body (Corpo)** é o que está dentro do pacote (Os dados do cartão de crédito).
5. O **Status Code** é a resposta do atendente. 
   - "Tudo certo, despachado" (201). 
   - "Faltou o CEP" (400).
   - "Você não pagou o selo" (401).
   - "Esse pacote já foi despachado antes!" (409 Conflict - A famosa proteção de Idempotência).

No Playwright, utilizamos a API de `request` (chamada de APIRequestContext) que é super rápida e não precisa abrir um navegador para fazer essas validações.

## 06. Exemplos

### Exemplo 1: POST para Criar um Pagamento Pix
```typescript
const response = await request.post('https://api.paymentgateway.com/v1/pix', {
  headers: {
    'Authorization': 'Bearer token-secreto-123',
    'Idempotency-Key': 'abc-123-uuid-unico'
  },
  data: {
    amount: 15000, // em centavos (R$ 150,00)
    description: 'Compra de Teclado Mecânico'
  }
});
```

### Exemplo 2: GET para Consultar o Status
```typescript
const getResponse = await request.get('https://api.paymentgateway.com/v1/pix/px_987654321', {
  headers: {
    'Authorization': 'Bearer token-secreto-123'
  }
});
```

## 07. Código comentado
Veja como organizamos um teste completo validando o fluxo de criação e erro de um pagamento em Playwright:

```typescript
import { test, expect } from '@playwright/test';

test.describe('API de Pagamentos - Criação de Pix', () => {
  
  test('Deve criar um pagamento Pix com sucesso (Status 201)', async ({ request }) => {
    // 1. Preparação (Arrange): Headers e payload
    const headers = {
      'Authorization': 'Bearer test_token_xyz',
      'Idempotency-Key': `idemp_${Date.now()}` // Garante unicidade
    };
    
    const payload = {
      amount: 5000, // R$ 50,00
      currency: 'BRL',
      customer_id: 'cus_12345'
    };

    // 2. Ação (Act): Dispara a requisição POST
    const response = await request.post('https://api-sandbox.meumeiodepagamento.com.br/v1/pix', {
      headers,
      data: payload
    });

    // 3. Validação (Assert)
    // Valida se a resposta foi 201 Created
    expect(response.status()).toBe(201);
    
    // Converte a resposta para JSON
    const responseBody = await response.json();
    
    // Valida a estrutura da resposta
    expect(responseBody).toHaveProperty('id');
    expect(responseBody.status).toBe('pending');
    expect(responseBody.qr_code).toBeDefined();
  });

  test('Deve retornar 422 ao tentar pagar com valor zerado', async ({ request }) => {
    const response = await request.post('https://api-sandbox.meumeiodepagamento.com.br/v1/pix', {
      headers: { 'Authorization': 'Bearer test_token_xyz' },
      data: {
        amount: 0, // Valor inválido
        currency: 'BRL'
      }
    });

    // Valida Erro de Negócio (Unprocessable Entity)
    expect(response.status()).toBe(422);
    
    const responseBody = await response.json();
    expect(responseBody.error.message).toBe('O valor do pagamento deve ser maior que zero.');
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Fazer uma requisição `GET` para buscar um pagamento existente e validar a resposta.

**Passo a passo:**
1. Crie um arquivo chamado `consulta-pagamento.spec.ts`.
2. Importe `test` e `expect` do `@playwright/test`.
3. Crie um bloco `test` chamado "Deve consultar um pagamento existente".
4. Use o `request.get()` passando a URL (pode usar o Reqres.in para simular, ex: `https://reqres.in/api/users/2` apenas para fins didáticos).
5. Extraia o `.json()` da resposta.
6. Faça um `expect(response.status()).toBe(200)`.
7. Faça um `expect` em algum campo do body retornado.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Simular um erro de Autenticação (`401 Unauthorized`).
- Crie um teste que faça um `POST` em um endpoint (pode simular com Reqres.in ou Restful-Booker).
- **Não** envie o header de `Authorization`.
- Valide se o `response.status()` retorna o código que representa Falha de Autenticação (Qual era mesmo? Consulte os conceitos!).
- Opcional: verifique se a mensagem de erro no corpo da resposta faz sentido.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Validar Idempotência (Prevenir duplicidade).
1. Faça um `POST` para criar um recurso (Pode ser num mock de API). Envie no Header a chave `Idempotency-Key: 'chave-unica-123'`.
2. Guarde o status da primeira resposta (deve ser sucesso, ex: 201).
3. Faça **exatamente a mesma requisição** `POST`, com o mesmo body e a mesma `Idempotency-Key`.
4. Valide que a API retorna o status `409 Conflict` (ou o mesmo resultado `200/201` original, mas *sem criar um novo id no banco* - dependendo de como a API mockada lida com idempotência). Tente implementar a validação de que a transação não foi duplicada!

## 11. Erros comuns
- **Esquecer o await:** `const response = request.post(...)` sem `await` vai gerar um objeto Promisse, e qualquer `response.status()` vai quebrar o teste.
- **Não validar Content-Type:** Algumas APIs de banco exigem `Content-Type: application/x-www-form-urlencoded` ao invés de `application/json`.
- **Confundir 401 com 403:** 
  - `401 Unauthorized`: Você não se identificou (Faltou token).
  - `403 Forbidden`: Você se identificou, mas não tem permissão de administrador para realizar aquele estorno.

## 12. Debugging
Se a sua chamada API estiver falhando:
- **Use console.log:** Imprima o corpo da resposta no terminal. Muitas vezes o 400 Bad Request traz a causa raiz no body.
  ```typescript
  console.log(await response.json());
  ```
- **Ferramentas de Rede:** Use o Postman ou Insomnia para montar a requisição primeiro, se lá funcionar e no Playwright não, compare os Headers gerados. O Playwright pode estar enviando headers padrão que interferem, ou faltando o `User-Agent`.

## 13. Aplicação no projeto principal
No nosso projeto, utilizaremos o `APIRequestContext` do Playwright para interagir com nossa API local de Gateway de Pagamento. Vamos validar extensivamente os **Status Codes**, pois um 422 retornado corretamente quando enviamos um CPF inválido é um critério de aceite (AC) tão importante quanto o caminho feliz. Usaremos muito o método PATCH para simular mudanças de status de transações via Webhooks.

## 14. Perguntas de entrevista
1. **Qual a diferença entre PUT e PATCH?**
   *Resposta esperada:* PUT substitui o recurso inteiro (se enviar só o nome, apaga os outros dados). PATCH atualiza parcialmente (se enviar só o nome, mantém os outros dados intactos). Em pagamentos, usamos muito PATCH para alterar apenas o status (ex: de PENDING para PAID).
2. **Em um sistema de transações, por que recebemos o erro 409 Conflict ou 422 Unprocessable Entity?**
   *Resposta esperada:* O 409 ocorre geralmente por causa de Idempotência ou tentativa de pagar a mesma fatura duas vezes. O 422 ocorre por falhas de regra de negócio, como tentar aprovar uma transação com cartão vencido ou saldo insuficiente (a requisição é sintaticamente correta, mas falha na semântica de negócios).

## 15. Checklist
- [ ] Entendo as diferenças entre GET, POST, PUT, PATCH e DELETE.
- [ ] Sei mapear as famílias de status HTTP (2xx, 4xx, 5xx) para os cenários de teste.
- [ ] Compreendo a importância dos Headers, em especial Authorization e Idempotency-Key.
- [ ] Consegui executar chamadas usando `request.get()` e `request.post()` no Playwright.

## 16. Critério para avançar
Você está pronto para avançar quando conseguir escrever, sem precisar copiar colar da documentação o tempo todo, um teste que faz um POST para uma API fictícia, envia um JSON e valida se a resposta foi HTTP 201 ou 400/422. A fluência em lidar com Promisses (`await`) e respostas HTTP é a base de todo o curso!
