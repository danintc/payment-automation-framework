# Fase 9: Contract Testing

## 01. O que você vai aprender
Nesta fase, você aprenderá a garantir que as APIs de pagamento estão se comunicando no formato exato que prometeram. Vamos focar em **Contract Testing (Testes de Contrato)** em tempo de execução usando o **Zod**, uma biblioteca de validação de schemas em TypeScript. Você vai aprender a definir a estrutura esperada de payloads de resposta (como transações via Pix e cartões), validar tipos de dados, lidar com campos opcionais e prevenir falhas catastróficas causadas por *breaking changes* (mudanças que quebram a integração) não anunciadas.

## 02. Por que isso importa para um QA
Imagine que seu parceiro de gateway de pagamento mude silenciosamente o campo `status` de `"approved"` (string) para `1` (number). O código do seu sistema que espera a string falhará miseravelmente, resultando em pedidos não processados e clientes furiosos.
Como SDET (Software Development Engineer in Test) de sistemas de pagamento, você não pode confiar apenas no *status code* 200 OK. É essencial verificar se o *shape* (formato) e os tipos dos dados retornados estão estritamente corretos. Testes de contrato garantem que qualquer mudança não planejada na estrutura da API seja interceptada pela sua automação antes de atingir a produção.

## 03. Pré-requisitos
- Compreensão sólida das fases anteriores (configuração do Playwright, automação de APIs REST).
- Entendimento de tipos básicos e avançados em TypeScript.
- Noções de como gateways de pagamento estruturam dados (como UUIDs, enums de status, timestamps ISO 8601).
- Zod instalado no projeto (`npm install zod`).

## 04. Conceitos
- **Testes de Contrato (Contract Testing):** Verificação de que o consumidor (nosso teste) e o provedor (a API) concordam com o formato das mensagens trocadas (o "contrato").
- **Zod:** Uma biblioteca TypeScript-first de declaração de schema e validação. Com ela, você define um modelo de dados apenas uma vez e ele serve tanto como um tipo TS quanto como um validador em tempo de execução.
- **Breaking Changes:** Modificações numa API que quebram aplicações consumidoras (ex: remover um campo obrigatório, mudar um tipo de dado).
- **Runtime Validation:** Diferente do TypeScript que checa tipos durante a compilação, a validação em tempo de execução (com Zod) checa os dados exatos vindos da rede no momento da execução do teste.

## 05. Explicação mastigada
No TypeScript puro, se você declara que uma resposta de API é do tipo `Transaction`, o TypeScript acredita em você na hora de compilar, mas se a API real retornar algo diferente, o teste só vai quebrar de forma confusa mais para a frente. 
O Zod atua como um "leão de chácara" no exato momento em que os dados chegam da API. Você cria um `Schema` do Zod (ex: `z.object({ id: z.string().uuid() })`). Quando a API responde, você manda o Zod analisar esse JSON (`schema.parse(responseBody)`). Se vier tudo certo, ótimo! O tipo do TS é inferido e o código continua seguro. Se a API mudou o contrato (exemplo, `id` não veio ou não é um UUID válido), o Zod dispara um erro claro e imediato: *"Faltou o campo X, que deveria ser Y"*. É o guardião do seu contrato.

## 06. Exemplos

### Schema Básico de Pagamento
```typescript
import { z } from 'zod';

// Definindo o contrato
const pixResponseSchema = z.object({
  transaction_id: z.string().uuid(),
  amount: z.number().positive(),
  currency: z.literal('BRL'),
  status: z.enum(['pending', 'approved', 'rejected']),
  qr_code: z.string().url(),
  created_at: z.string().datetime() // ISO 8601
});

// Extraindo o tipo TS automaticamente
type PixResponse = z.infer<typeof pixResponseSchema>;
```

### Validação em um Teste Playwright
```typescript
const response = await request.post('/api/v1/pix/generate', { data: payload });
const responseBody = await response.json();

// Valida o contrato (lança erro e falha o teste se não bater)
const validatedData = pixResponseSchema.parse(responseBody); 
```

## 07. Código comentado

```typescript
import { test, expect } from '@playwright/test';
import { z } from 'zod';

// 1. Definimos o contrato esperado para a resposta de liquidação de cartão de crédito
const creditCardCaptureSchema = z.object({
  id: z.string().startsWith('ch_'), // IDs de charge geralmente têm prefixos
  amount: z.number().int().positive(), // Em centavos, deve ser inteiro positivo
  status: z.literal('succeeded'),
  payment_method: z.object({
    card_brand: z.string(),
    last4: z.string().length(4), // Exatamente 4 dígitos
  }),
  metadata: z.record(z.string()).optional(), // Objeto opcional com chave/valor string
});

test('Deve capturar pagamento de cartão respeitando o contrato', async ({ request }) => {
  const res = await request.post('/api/v1/charges/capture', {
    data: { charge_id: 'ch_123456789' }
  });
  
  expect(res.ok()).toBeTruthy();
  const data = await res.json();

  // 2. parse() joga uma exceção detalhada (ZodError) se o payload não seguir o contrato.
  // safeParse() não joga erro, mas retorna { success: false, error } que é útil se
  // você quiser formatar o erro manualmente no Playwright.
  const parsed = creditCardCaptureSchema.safeParse(data);
  
  // 3. Verificamos se teve sucesso e, se não, exibimos o erro formatado no expect
  expect(parsed.success, `Falha no contrato de captura de cartão: ${parsed.error?.message}`)
    .toBeTruthy();
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Criar um teste que valide o contrato de uma API de Webhooks de estorno (Refund).

1. No seu arquivo de testes, crie um schema do Zod chamado `webhookRefundSchema`.
2. O webhook deve ter os campos: `event_id` (string uuid), `event_type` (deve ser exatamente a string `"refund.processed"`), e `data` (um objeto).
3. Dentro do `data`, deve haver `refund_id` (string), `amount` (número positivo), e `reason` (enum: `"fraud"`, `"customer_request"`, `"duplicate"`).
4. Faça uma requisição GET para `/api/v1/events/latest` (use um mock ou ambiente de teste) para pegar o último evento de refund.
5. Use `.parse()` ou `.safeParse()` para validar o JSON da resposta contra o seu `webhookRefundSchema`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Validar um contrato mais complexo com arrays e campos nulos para faturas (Invoices).

Você está testando a listagem de faturas. A API `/api/v1/invoices` retorna um objeto contendo uma propriedade `items` que é um array.
- Crie o schema para um item da fatura: `id` (string), `description` (string), `amount` (número), `discount` (número ou nulo). *Dica: use `z.nullable()`*.
- Crie o schema pai `invoiceResponseSchema` que contém `total` (número) e `items` (array do schema criado acima). *Dica: use `z.array()`*.
- Faça a requisição e garanta que o array não venha vazio antes de validar o contrato.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Sistema de validação global usando Fixtures.

Atualmente, você precisa chamar o Zod em todo arquivo de teste.
Desafio:
1. Crie uma Playwright Fixture customizada chamada `apiContract`.
2. Essa fixture deve receber a resposta do Playwright (o `APIResponse` ou o JSON direto) e o Schema do Zod.
3. Se a validação falhar, a fixture deve formatar o `ZodError` para mostrar uma tabela legível no console indicando qual campo exato falhou (ex: `caminho: payment_method.last4, erro: "Deve conter 4 caracteres"`).
4. Use essa fixture nos seus testes de fluxo de pagamento para limpar o código do teste e centralizar o log de erros de contrato.

## 11. Erros comuns
- **Achar que `Type` do TS protege contra payload real:** TypeScript não existe em runtime. Declarar `const data: Resposta = await res.json()` não impede que um número venha no lugar de uma string. Zod resolve isso.
- **Não permitir campos extras:** Por padrão, o Zod ignora chaves extras (`strip`), o que é geralmente bom. Mas se as regras do gateway ditam que chaves desconhecidas devem falhar (para segurança), use `.strict()` no schema.
- **Deixar o teste falhar com mensagens crípticas:** O ZodError cru pode ser longo e difícil de ler num report de CI/CD. Sempre pegue o erro e formate ou use `.safeParse` + `expect`.

## 12. Debugging
Se o seu teste de contrato quebrar (e vai quebrar bastante em ambientes de desenvolvimento onde o backend está iterando rápido):
1. **Analise o `ZodError`:** O Zod diz exatamente onde está a falha. Exemplo: `error.issues[0].path` vai te dar o caminho exato do JSON (ex: `['data', 'user', 'age']`).
2. **Imprima o payload real:** Antes do parse, faça um `console.log(JSON.stringify(data, null, 2))` para comparar o que a API mandou versus o que seu Schema espera.
3. **Zod version mismatch:** Confirme se a versão do Zod que você usa e a documentação que lê não divergem, especialmente para regras complexas de validação como regex ou transformações.

## 13. Aplicação no projeto principal
No seu ecossistema de testes de pagamento, os schemas do Zod podem (e devem) ser compartilhados. Se a sua empresa usa TypeScript no backend e frontend, você pode colocar os schemas num repositório comum (package npm) e importar nos testes do Playwright. 
Isso significa que, se um desenvolvedor modificar o contrato no backend, os tipos falharão na compilação ou, no mínimo, seus testes quebrarão instantaneamente no CI alertando da *breaking change*. Você aplicará isso validando os fluxos cruciais: Criação de Token de Cartão, Geração de Pix e Webhooks de Liquidação.

## 14. Perguntas de entrevista
1. **Qual a diferença entre validação estática no TypeScript e validação de runtime com Zod?**
   *Resposta esperada:* TS valida o código enquanto você escreve/compila. Se a API de pagamento retornar dados diferentes em produção, o TS não tem como saber. Zod checa os dados de fato no momento que chegam, disparando erros reais (runtime) se a estrutura não bater.
2. **Como você protegeria sua automação de mudanças não documentadas na API do Gateway?**
   *Resposta esperada:* Criando testes de contrato para todos os payloads recebidos, validando tipos rigorosos (como limites de caracteres ou UUIDs) e rodando esses testes contra o ambiente de sandbox do gateway diariamente.
3. **O que é uma 'breaking change' em uma API REST e como o Contract Testing ajuda?**
   *Resposta esperada:* É uma mudança no contrato (remover campos, mudar tipos, alterar estrutura) que quebra quem está consumindo. Testes de contrato (via Zod/Pact) detectam isso rapidamente impedindo deploys perigosos.

## 15. Checklist
- [ ] Zod instalado no projeto Playwright.
- [ ] Criou o primeiro Schema Zod validando `string()`, `number()` e `enum()`.
- [ ] Compreendeu a diferença entre `.parse()` e `.safeParse()`.
- [ ] Validou o shape de uma resposta aninhada (ex: um pagamento com `payment_method` embutido).
- [ ] Escreveu asserções robustas e amigáveis para falhas de contrato.

## 16. Critério para avançar
Você pode prosseguir para a próxima fase quando for capaz de interceptar um JSON de uma API de pagamento, submetê-lo a uma validação rígida via Zod schema, lidando com campos opcionais, arrays e tipos específicos (como UUID e URLs), e apresentando uma falha de teste clara caso a API sofra uma alteração de contrato.
