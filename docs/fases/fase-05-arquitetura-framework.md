# Fase 5: Arquitetura de Framework

## 01. O que você vai aprender
Nesta fase, você deixará de escrever "scripts" isolados e aprenderá a criar uma **arquitetura de testes robusta e escalável** voltada para APIs complexas, como as de pagamentos. Você aprenderá a:
- Aplicar o **Service Object Pattern** para isolar a camada HTTP da camada de lógica e asserções de teste.
- Trabalhar com **DTOs (Data Transfer Objects)** em TypeScript para garantir tipagem estrita de contratos.
- Utilizar **Fixtures customizadas** do Playwright para injeção nativa de dependências.
- Separar responsabilidades no framework, facilitando a manutenção e a reutilização de código.

## 02. Por que isso importa para um QA
Escrever testes com o formato de scripts (fazendo requisições manuais `request.post('/url')` espalhadas por dezenas de arquivos) é uma receita para o fracasso a longo prazo. No domínio de pagamentos, uma mudança de contrato na rota de "Captura de Transação" impactaria inúmeros testes.
Com uma arquitetura modularizada:
- Se uma URL ou header (ex: `X-Correlation-ID`) muda, você ajusta em um só lugar (no *Client*).
- O autocompletar da sua IDE evita erros de digitação em *payloads* graças aos DTOs.
- Seus testes se tornam auto-documentados e expressam regras de negócio, enquanto a complexidade de redes fica escondida nos bastidores. 
Isso separa um Analista de Testes que aperta botões de um verdadeiro **Engenheiro de Qualidade (SDET)**.

## 03. Pré-requisitos
- Conhecimentos sólidos nos verbos HTTP e códigos de status.
- Compreensão básica de Orientação a Objetos em TypeScript (Classes, Herança, Interfaces).
- Ter executado testes de API simples com a classe nativa `APIRequestContext` do Playwright.

## 04. Conceitos
- **Service Object Pattern:** Semelhante ao *Page Object Pattern* em UI, os Service Objects encapsulam os endpoints (URLs, headers e regras de serialização). Eles expõem métodos de alto nível para os testes (ex: `paymentClient.createPayment(payload)`).
- **DTOs (Data Transfer Objects):** Interfaces que definem estritamente a forma dos dados que transitam para a API (Requests) ou voltam dela (Responses). Impedem que você envie acidentalmente strings onde devem ser números (ex: o crítico `amountInCents`).
- **Fixtures (Injeção de Dependência):** Mecanismo nativo do Playwright que gerencia o ciclo de vida (Setup/Teardown) de objetos (banco, tokens, service clients). Em vez de você instanciar classes manualmente com `new` em um `beforeEach`, as Fixtures preparam os recursos automaticamente apenas quando o teste solicita.

## 05. Explicação mastigada
Pense em um restaurante requintado:
- O **Teste** é o cliente fazendo o pedido na mesa.
- O **Service Object** é o Garçom. Ele sabe como ir até a cozinha, por qual porta entrar e como entregar o pedido de forma segura.
- O **DTO** é o cardápio. Ele garante que o cliente não peça "carne de dinossauro" quando o sistema só aceita "frango" ou "carne bovina".
- As **Fixtures** formam o sistema administrativo do restaurante: garantem que o garçom seja posicionado ao lado da sua mesa assim que você senta, e dispensam o funcionário assim que você termina de comer.

No teste de API, seu teste deve ser simples e limpo. Ele pede para o Service Object executar uma ação passando o DTO, e o Service Object retorna o prato pronto (o `APIResponse`), onde o teste vai apenas julgar se está "saboroso" (asserções).

## 06. Exemplos
A estrutura de diretórios do nosso framework passará a ter esta organização:
```text
api-automation-framework/
├── src/
│   ├── clients/                  # Service Objects (camada HTTP)
│   │   ├── BaseClient.ts
│   │   └── PaymentClient.ts
│   ├── fixtures/                 # Injeção de dependências do Playwright
│   │   └── apiFixtures.ts
│   └── models/                   # Tipagens estritas e DTOs
│       └── payment.types.ts
├── tests/
│   └── payments.spec.ts          # Arquivos de Teste limpos
└── playwright.config.ts
```

## 07. Código comentado

### Passo 1: O DTO (Models)
Definimos os contratos de dados para garantir precisão e prever comportamentos. Em sistemas financeiros operamos sempre com centavos em números inteiros (ex: `amountInCents: 1000` = R$ 10,00).

```typescript
// src/models/payment.types.ts
export type PaymentMethod = 'CREDIT_CARD' | 'PIX' | 'BOLETO';

export interface CreatePaymentDTO {
  amountInCents: number; 
  currency: 'BRL' | 'USD';
  customerId: string;
  paymentMethod: PaymentMethod;
  metadata?: Record<string, string>; // Dados adicionais flexíveis
}
```

### Passo 2: O Base Client
Uma classe abstrata que concentra comportamentos comuns a todas as requisições (ex: injetar UUIDs de correlação e *headers* padrão).

```typescript
// src/clients/BaseClient.ts
import { APIRequestContext, APIResponse } from '@playwright/test';
import { randomUUID } from 'node:crypto';

export abstract class BaseClient {
  protected constructor(
    protected readonly request: APIRequestContext,
    protected readonly baseURL: string
  ) {}

  // O encapsulamento POST que adiciona um rastreador automático
  protected async post(
    endpoint: string,
    data: unknown,
    headers?: Record<string, string>
  ): Promise<APIResponse> {
    return this.request.post(`${this.baseURL}${endpoint}`, {
      data,
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': randomUUID(), // Header para rastreabilidade de logs
        ...headers,
      },
    });
  }
}
```

### Passo 3: O Service Object Específico
Herda do BaseClient e modela exatamente as operações de pagamento.

```typescript
// src/clients/PaymentClient.ts
import { APIRequestContext, APIResponse } from '@playwright/test';
import { BaseClient } from './BaseClient';
import { CreatePaymentDTO } from '../models/payment.types';

export class PaymentClient extends BaseClient {
  constructor(request: APIRequestContext, baseURL: string) {
    super(request, baseURL);
  }

  // Abstraímos a rota e passamos opções extras sem poluir o teste
  async createPayment(
    payload: CreatePaymentDTO,
    options?: { idempotencyKey?: string; token?: string }
  ): Promise<APIResponse> {
    const headers: Record<string, string> = {};
    if (options?.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;
    if (options?.token) headers['Authorization'] = `Bearer ${options.token}`;
    
    return this.post('/v1/payments', payload, headers);
  }
}
```

### Passo 4: As Fixtures do Playwright
Aqui ocorre a mágica da injeção de dependência. Sobrescrevemos o método nativo `test` do Playwright para embutir nossos Clients.

```typescript
// src/fixtures/apiFixtures.ts
import { test as base, expect } from '@playwright/test';
import { PaymentClient } from '../clients/PaymentClient';

type ApiFixtures = {
  paymentClient: PaymentClient;
  merchantToken: string;
};

export const test = base.extend<ApiFixtures>({
  // Fixture de Autenticação gerada dinamicamente
  merchantToken: async ({ request }, use) => {
    // Código para obter um token real...
    const fakeToken = "ey.JhbGciOiJIUzI1Ni.s_token_mock";
    await use(fakeToken); // Entrega a dependência para o teste
  },

  // Fixture do Service Object (depende do request nativo)
  paymentClient: async ({ request }, use) => {
    const baseURL = process.env.API_BASE_URL || 'http://localhost:3000';
    const client = new PaymentClient(request, baseURL);
    await use(client);
  },
});

export { expect }; // Exportamos expect para não precisar importar do base
```

### Passo 5: O Teste Limpo
Agora, em vez de importar configurações de request manuais, apenas consumimos as fixtures pelo seu nome dentro dos parâmetros do teste.

```typescript
// tests/payments.spec.ts
import { test, expect } from '../src/fixtures/apiFixtures';
import { CreatePaymentDTO } from '../src/models/payment.types';

test.describe('Processamento de Pagamentos', () => {
  // Chamamos paymentClient e merchantToken destruturados. 
  // O Playwright os injeta magicamente.
  test('deve autorizar um pagamento de cartão válido', async ({ paymentClient, merchantToken }) => {
    const payload: CreatePaymentDTO = {
      amountInCents: 15000,
      currency: 'BRL',
      customerId: 'cus_12345',
      paymentMethod: 'CREDIT_CARD'
    };

    // Foco do teste está apenas na regra de negócio
    const res = await paymentClient.createPayment(payload, { token: merchantToken });
    const body = await res.json();

    expect(res.status()).toBe(201);
    expect(body.status).toBe('AUTHORIZED');
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Criar um modelo e um Service Object para buscar Estornos (Refunds).
1. Em `src/models/payment.types.ts`, crie a interface `RefundDTO` contendo `amountInCents` e `reason`.
2. Em `src/clients/PaymentClient.ts`, crie o método `async refund(id: string, payload: RefundDTO, token: string)`.
3. Utilize o método `this.post` apontando para `/v1/payments/${id}/refund`.
4. Escreva um pequeno teste usando o `paymentClient` na fixture testando um reembolso.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
A nova funcionalidade de Pix exige uma rota exclusiva: `POST /v2/pix/charges`.
Crie uma arquitetura independente para o Pix:
- Crie o arquivo de tipagem `pix.types.ts` com um DTO `PixChargeDTO`.
- Crie o `PixClient.ts` que estende de `BaseClient`.
- Insira o `pixClient` como uma nova dependência em `src/fixtures/apiFixtures.ts`.
- Crie o arquivo `tests/pix.spec.ts` consumindo a nova fixture `pixClient`.

## 10. Desafio (Nível 3 - Challenge)
**Refatoração Hardcore:** Você recebeu um script legado monstruoso, com URLs marretadas no código, nenhum padrão e sem autenticação reaproveitável. O arquivo `legacy.spec.ts` faz múltiplos `request.post` repetitivos montando headers em todas as linhas.
Seu desafio:
1. Criar um Client completo unindo todas as rotas esparsas da API de Adquirência.
2. Identificar e extrair todas as regras comuns para a abstração do BaseClient.
3. Tipar todas as variações de payload que o QA anterior passava como `{ "valor": "100.00" }` (corrigindo a falha arquitetural de ponto flutuante, transformando para `amountInCents: 10000`).

## 11. Erros comuns
- **Retornar o Body em vez da Response no Client:** Jamais faça seu método no Service Object retornar `await request.json()`. Se a API estourar um Erro 500 ou HTML do NGINX, seu JSON parse vai quebrar o teste impedindo que você faça asserções úteis no HTTP Status de retorno. Retorne sempre o objeto `APIResponse`.
- **Instanciar o Client com `new` dentro de um BeforeEach:** Embora funcione, isso derrota o propósito do Playwright, tirando as vantagens de concorrência paralela limpa e polindo arquivos de teste com imports desnecessários. Use Fixtures!
- **Usar o tipo `any`:** Não use DTOs tipados como `any` nos payloads, isso abre margem para erros bobos de escrita em objetos durante a manutenção da suíte.

## 12. Debugging
- **Fixture quebrando?** Se sua Fixture depende de uma API externa para gerar um token e ela falha, todos os testes falharão imediatamente. Use `console.log` no hook da Fixture antes de chamar o `use()` para inspecionar os tokens recuperados.
- **Requisições falhando misteriosamente?** Adicione um logger simples na classe `BaseClient.ts` antes de retornar o POST ou GET para visualizar a URL exata e os cabeçalhos que estão sendo montados por debaixo dos panos.

## 13. Aplicação no projeto principal
Em nosso ecossistema real de meios de pagamentos (com liquidações, split, adquirentes e antifraude), os cenários são complexos, exigindo testes envolvendo Idempotência e Concorrência. Separar a infraestrutura de rede da lógica de teste é o **requisito inegociável** para lidar com webhooks enfileirados, mock servers (Toxiproxy) e validações em banco de dados de maneira manutenível, como veremos nas próximas fases.

## 14. Perguntas de entrevista
- *"Como você gerencia o setup de autenticação de suas automações de API para evitar gargalos?"*
  **Resposta:** Eu utilizo as Fixtures customizadas do Playwright. Gero o token apenas uma vez ou encapsulo sua geração de forma limpa na fixture. O teste final apenas pede a propriedade `token` sem saber como ele foi gerado.
- *"O que é e por que usar o Service Object Pattern?"*
  **Resposta:** É o análogo do Page Object, aplicado em APIs. Ele isola a formação da requisição HTTP (endpoint, formatação, cabeçalhos) das asserções, promovendo reuso.
- *"Por que mapear DTOs para inputs de testes de API em vez de enviar objetos JavaScript crus?"*
  **Resposta:** DTOs proporcionam tipagem estrita (garantindo tipos, como ausência de pontos flutuantes em gateways de pagamento), auto-documentam a estrutura esperada pela API e evitam que desenvolvedores/QAs comecem a usar chaves erradas em manutenções futuras.

## 15. Checklist
- [ ] Compreendeu o padrão de Service Objects isolando a requisição da asserção.
- [ ] Entendeu o papel de DTOs mapeando tipos robustos via TypeScript.
- [ ] Sabe a diferença estrutural entre instanciar objetos manualmente e usar o recurso de Fixtures.
- [ ] Compreende que Clients de API devem sempre retornar respostas brutas (`APIResponse`) para testes flexíveis de casos negativos.

## 16. Critério para avançar
Você está apto a prosseguir quando for capaz de estender uma classe `BaseClient` para adicionar um novo módulo de endpoint e conseguir injetá-lo com sucesso em um arquivo `.spec.ts` por meio do sistema de *Fixtures* do Playwright sem erros de TypeScript.
