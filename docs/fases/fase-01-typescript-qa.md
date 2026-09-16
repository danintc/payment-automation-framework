# Fase 1: TypeScript para QA Automation

## 01. O que você vai aprender
- Os fundamentos essenciais e avançados do TypeScript, focados no que realmente usamos em testes de API e automação com Playwright.
- A diferença prática entre `type` e `interface` na modelagem de payloads de pagamento.
- Como utilizar **Utility Types** (`Pick`, `Omit`, `Partial`) para reaproveitar contratos de APIs.
- A criação de **Generics** para construir tipagens dinâmicas, como uma função genérica de requisição HTTP que sabe exatamente o que vai retornar dependendo do endpoint (ex: Pix vs. Cartão de Crédito).
- Asserções de tipo (`as Type`) de forma segura, evitando *type casting* perigoso que esconde bugs.

## 02. Por que isso importa para um QA
Como SDET (Software Development Engineer in Test), você não está apenas escrevendo scripts de teste, está construindo um ecossistema de qualidade de software sustentável e escalável. 
Em sistemas de pagamento, as APIs trafegam dados extremamente sensíveis e com contratos complexos (ex: chaves Pix idempotentes, valores transacionais, webhooks de status). 
Se você usa JavaScript puro ou "Typescript preguiçoso" (enchendo o código de `any`), você perde o poder do *intellisense*, o *auto-complete* e, pior, permite que o seu teste quebre na execução porque uma propriedade do payload mudou de nome ou foi digitada errada.
TypeScript bem aplicado garante **Shift-Left**: o erro do teste é pego no momento em que você escreve a automação, antes mesmo de executá-la.

## 03. Pré-requisitos
- Conhecimento básico em lógica de programação e JavaScript (variáveis, funções, arrays, objetos).
- Node.js instalado na máquina.
- VS Code (ou sua IDE de preferência) configurado.
- Familiaridade básica com conceitos de API REST (GET, POST, Body, Status Code).

## 04. Conceitos
- **Type / Interface**: Formas de definir a estrutura de objetos e payloads. Em APIs de pagamento, usamos para mapear fielmente o *request body* e o *response body* com base no Swagger/OpenAPI.
- **Utility Types (Tipos Utilitários)**: Operações avançadas sobre tipos existentes. 
  - `Omit<T, K>`: Remove as propriedades K do tipo T (ex: Criar um payload de requisição baseando-se no modelo de resposta, mas omitindo o campo `id` que é autogerado pelo banco de dados).
  - `Pick<T, K>`: Escolhe apenas as propriedades K do tipo T (ex: Pegar apenas `status` e `transactionId` de um objeto massivo de Charge para validar um Webhook).
- **Generics (`<T>`)**: Permitem que funções, classes ou interfaces trabalhem com diversos tipos, mas de forma fortemente segura. Em vez de dizer "esta função retorna algo (any)", dizemos "esta função retorna o Tipo T que eu repassar a ela dinamicamente".
- **Strict Mode**: Configuração fundamental do compilador `tsconfig.json` (`"strict": true`) que obriga o seu código de testes a ser à prova de balas (ex: impede variáveis que podem ser nulas ou undefined de serem operadas sem checagem prévia).

## 05. Explicação mastigada
Imagine que a API de Pagamento da sua empresa possua um contrato para criar transações via Pix e outro via Cartão de Crédito. 
Ambas as requisições têm campos centrais em comum (como `valor` e `moeda`), mas o Cartão exige o objeto `dadosDoCartao` enquanto o Pix não.

Se usarmos JavaScript puro (sem tipagem):
```javascript
const payload = { valr: 1000, moeda: 'BRL', tipo: 'PIX' }; // Ops, digitei 'valr' em vez de 'valor'
```
O script vai rodar, enviar um request inválido para a API de pagamentos, receber um `400 Bad Request`, e você pode perder horas de debug até perceber que foi um *typo* (erro de digitação) no payload, e não um bug genuíno da aplicação.

Com TypeScript e Interfaces:
```typescript
interface BasePayment {
  valor: number;
  moeda: string;
}
interface PixPayment extends BasePayment {
  chavePix: string;
}
const payload: PixPayment = { valr: 1000, moeda: 'BRL', chavePix: '123' }; // ERRO IMEDIATO NA IDE!
```
A IDE avisa instantaneamente com o erro vermelho: *"Object literal may only specify known properties, and 'valr' does not exist in type 'PixPayment'."*

O mais importante é: com os utilitários como `Omit`, não precisamos ficar recriando o mesmo objeto várias vezes para requisições similares. A manutenção fica limpa e centralizada.

## 06. Exemplos
Vejamos como aplicar Utility Types em um contexto de validação de banco de dados e APIs de pagamento.

```typescript
// Modelo base de uma transação conforme ela existe no Banco de Dados
export interface Transaction {
  id: string;
  amount: number;
  currency: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'REFUNDED';
  paymentMethod: 'PIX' | 'CREDIT_CARD';
  createdAt: string;
  updatedAt: string;
}

// Quando mandamos o POST para criar, não enviamos id, status, nem timestamps.
// Em vez de duplicar código criando outra interface, derivamos com Omit:
export type CreateTransactionRequest = Omit<Transaction, 'id' | 'status' | 'createdAt' | 'updatedAt'>;

// Validando um Webhook de notificação focado apenas no status.
// O Pick extrai cirurgicamente apenas os campos necessários.
export type WebhookStatusPayload = Pick<Transaction, 'id' | 'status'>;

const webhookData: WebhookStatusPayload = {
  id: 'txn_123456',
  status: 'APPROVED'
};
```

## 07. Código comentado

No contexto do **Playwright**, Generics brilham ao criarmos clientes HTTP base. Em vez de chamarmos `request.post` repetidamente escrevendo código sujo, centralizamos em uma função abstrata:

```typescript
import { APIRequestContext, APIResponse } from '@playwright/test';

/**
 * Helper genérico para chamadas POST.
 * O generic <TResponse> especifica o que a API vai devolver.
 * O generic <TRequest> garante que o payload enviado está correto.
 */
export async function postData<TResponse, TRequest>(
  requestContext: APIRequestContext,
  endpoint: string,
  payload: TRequest
): Promise<{ status: number; body: TResponse }> {
  
  // Realiza o request POST do Playwright, enviando o genérico payload
  const response: APIResponse = await requestContext.post(endpoint, {
    data: payload
  });

  // Extraímos o JSON. Com 'as TResponse', dizemos ao compilador que 
  // confiamos que este endpoint vai retornar aquele formato específico.
  const body = (await response.json()) as TResponse;

  return {
    status: response.status(),
    body: body
  };
}

// === Como isso seria consumido em um arquivo de teste de Gateway? ===

interface PixReq {
  amount: number;
  pixKey: string;
}

interface PixRes {
  transactionId: string;
  qrCode: string;
}

// A IDE vai exigir que o último parâmetro (body) possua 'amount' e 'pixKey'
// E garantirá que result.body terá as propriedades 'transactionId' e 'qrCode'
// const result = await postData<PixRes, PixReq>(request, '/v1/payments/pix', { amount: 50, pixKey: 'email@teste.com' });
```

## 08. Exercício guiado (Nível 1 - Guided)

**Objetivo:** Modelar a estrutura para o fluxo de estorno parcial (Refund) de um Charge de Cartão de Crédito.

**Passo a passo:**
1. Crie um arquivo chamado `refund.types.ts`.
2. Escreva uma `interface Refund` contendo as propriedades finais consolidadas do sistema: `refundId` (string), `chargeId` (string), `amountToRefund` (number) e `reason` (string).
3. A nossa API que faz o estorno inicial no POST não aceita o `refundId` (ele é gerado pelo servidor de autorização). Crie um tipo `RefundRequest` usando `Omit` baseado na interface `Refund`.
4. Crie uma constante e tente atribuir valores usando o seu novo tipo.

**Solução Exemplo:**
```typescript
// 1 e 2. Interface completa do domínio
export interface Refund {
  refundId: string;
  chargeId: string;
  amountToRefund: number;
  reason: string;
}

// 3. Omitindo o ID da requisição usando Utility Type
export type RefundRequest = Omit<Refund, 'refundId'>;

// 4. Instanciando o payload de envio
const payloadDeEstorno: RefundRequest = {
  chargeId: 'ch_999888_xyz',
  amountToRefund: 25.50,
  reason: 'Cliente contestou a cobrança'
  // Tente adicionar "refundId" aqui e assista o TypeScript te bloquear com segurança.
};
```

## 09. Exercício sozinho (Nível 2 - Semi-guided)

**Objetivo:** Tipar o fluxo de consulta de saldo e conciliação (Balance).

**Instruções:**
- Suponha que o modelo raiz do seu sistema de Ledger (Livro-razão) seja o seguinte:
```typescript
interface LedgerAccount {
  accountId: string;
  merchantName: string;
  availableBalance: number;
  blockedBalance: number;
  status: 'ACTIVE' | 'BLOCKED' | 'PENDING_KYC';
  lastReconciliationAt: string;
}
```
- A API `/v1/balance` retorna apenas informações parciais por segurança. Crie um tipo chamado `BalanceResponse` contendo **apenas** `accountId`, `availableBalance` e `blockedBalance`.
- Utilize o utilitário `Pick` para obter esse resultado.
- Crie um objeto fixo simulando um *mock* da resposta da API usando o tipo gerado.

## 10. Desafio (Nível 3 - Challenge)

**Objetivo:** Criar um **Generic Type Guard** de validação de sucesso ou erro (Error Handling para API de Pagamentos).

Nos gateways de pagamento, você frequentemente lida com um payload de sucesso e um padrão genérico para `422 Unprocessable Entity` ou `400 Bad Request`.

- Escreva uma interface `PaymentError` contendo `errorCode` (string), `message` (string) e `declineReason` (opcional, string).
- Crie um tipo genérico chamado `ApiResponse<T>` que seja uma união (Union Type `|`): ou o resultado é do tipo `T` (sucesso), ou do tipo `PaymentError` (erro).
- Crie uma função **Type Guard** genérica: `function isPaymentError<T>(response: ApiResponse<T>): response is PaymentError`. Dentro dessa função, avalie se existe a propriedade `errorCode` no objeto (dica: faça uma checagem de tipo `(response as PaymentError).errorCode !== undefined`).

## 11. Erros comuns
- **Abuso criminoso de `any`:** O uso excessivo de `any` em testes de API é pedir para ter problemas. Se um tipo puder variar dinamicamente ou for desconhecido no escopo inicial, utilize `unknown` e implemente verificações de Narrowing.
- **Confundir Tipagem Estática (TS) com Validação de Runtime:** Lembre-se, os tipos de TS somem quando compilados para JS. Se sua interface de Request diz que `amount` é `number`, mas o servidor lhe devolver uma `string`, o TS não te defenderá na hora que o script rodar. O TS protege o que você escreve, enquanto no Playwright garantimos o runtime com as ferramentas de *expect*.
- **Code Duplication (Payloads idênticos):** Criar três interfaces gigantescas para `PostCharge`, `GetCharge` e `UpdateCharge` invés de declarar o super-contrato de domínio e compor suas variações com `Pick`, `Omit`, `Partial` e `Required`. Isso duplica o esforço e desestabiliza caso a base mude.

## 12. Debugging
- **Erro: "Property 'x' does not exist on type 'unknown'"**: Extremamente comum quando você faz `const body = await response.json();` e em seguida tenta ler `expect(body.status)`. O Playwright retorna `any` ou você forçou `unknown`.
  - *Ação:* Use TypeScript *Type Casting* se confiar na estrutura `const body = await response.json() as MinhaInterfaceDeResponse` ou consuma um helper genérico com generics `<TResponse>`.
- **Analisando Utility Types Complexos na IDE**: É comum empilhar operações (ex: `Partial<Omit<Model, 'id'>>`). Se ficar confuso, basta passar o cursor em cima do nome do tipo criado no VS Code. O tooltip irá desembrulhar (expandir) as chaves finais permitidas para você ver exatamente a configuração computada do contrato.

## 13. Aplicação no projeto principal
Neste curso, criaremos do zero um Framework Playwright direcionado a um **Gateway de Pagamento Mockado**.
Em nossa arquitetura, teremos uma pasta `src/types` ou `src/models`. A documentação fornecida pelo "swagger do serviço" (como `/charge`, `/refund`, `/customers`) será transposta fielmente para TypeScript. 
Ao escrevermos a suíte de automação `charge-credit-card.spec.ts`, passaremos todos os requests através do nosso API Client customizado com Generics, usufruindo da capacidade completa do *intellisense*, o que nos dará confiança e velocidade absurdamente maior que em JavaScript convencional.

## 14. Perguntas de entrevista
1. **Pergunta:** Explique tecnicamente a principal diferença entre `type` e `interface` em TypeScript. Em qual cenário você usaria cada um?
   **Resposta:** `interface` permite trabalhar sob paradigmas orientados a objetos, suportando `extends` e *declaration merging* (poder declarar a mesma interface múltiplas vezes para adicionar campos). Em automação, é a base primária de modelos (Models). O `type` é um apelido (alias) incrivelmente flexível, adequado principalmente para unir tipos (Union Types, ex: `type Methods = 'GET' | 'POST'`) ou manipular utilitários (ex: `type Dto = Omit<Interface, 'id'>`).
2. **Pergunta:** Para que servem o `Omit` e o `Pick` no TypeScript? Por que não apenas criar tipos separados?
   **Resposta:** A utilização desses utilitários respeita o princípio DRY (Don't Repeat Yourself). Em microsserviços de pagamento, há frequentemente um modelo macro de transação. Para enviar num POST sem um ID gerado pelo sistema, um `Omit` resolve derivando um DTO confiável a partir daquele modelo principal de forma nativa e autoatualizável.
3. **Pergunta:** Como você aplica e justifica o uso de Typescript *Generics* em um framework focado em testes de API com Playwright?
   **Resposta:** Usamos *Generics* para padronizar e isolar funções estruturais, como os dispatchesc HTTP do Playwright. Posso criar uma abstração `sendRequest<TResponse, TPayload>` e repassá-la por todo o sistema. Seja validando clientes ou estornos bancários, meu retorno de `body` virá fortemente e precisamente tipado conforme o endpoint, tornando o código de testes imune a *type castings* errados pelo time de QA.

## 15. Checklist
- [ ] Entendi a diferença de uso prático entre Interfaces (modelos padrão) e Types (uniões e utilitários derivados).
- [ ] Consigo usar `Pick` e `Omit` para reaproveitar os contratos sem duplicar código.
- [ ] Compreendo a sintaxe de *Generics* `<T>` e como injetá-las em funções (HTTP Requests).
- [ ] Percebi que tipar rigorosamente no momento de escrever os testes economiza dias na manutenção a longo prazo do repositório Playwright.
- [ ] Finalizei e entendi todos os exercícios (Levels 1, 2 e 3) propostos.

## 16. Critério para avançar
Para pular e mergulhar fundo na Próxima Fase (onde iremos gerar o core da nossa arquitetura estrutural do repositório em Playwright), você precisa bater o olho em um JSON massivo de resposta de webhook e imediatamente idealizar no papel como abstraí-lo para Interfaces do TypeScript usando utilitários caso precise gerar requisições de teste partindo dos mesmos dados.
Se o conceito de *Generics* soa complexo e meio abstrato, não tenha receio! Na Fase 2 implementaremos o nosso Cliente HTTP base ao vivo e você presenciará como é simples a sua usabilidade!
