# Fase 15: Observabilidade e Debugging

## 01. O que você vai aprender
- O conceito de **Observabilidade** em sistemas distribuídos (logs, métricas e traces).
- Como funciona o **Distributed Tracing** e a importância do `X-Correlation-ID` (ou `Trace-ID`).
- Como injetar e capturar Headers de correlação usando Playwright.
- Estratégias de **Logging** em testes de API automatizados.
- Técnicas avançadas para **debuggar** falhas de testes em pipelines de CI/CD (GitHub Actions, GitLab CI, etc).
- Como correlacionar uma falha de teste com os logs da aplicação backend.

## 02. Por que isso importa para um QA
Em ecossistemas de pagamentos modernos, uma única requisição de "Checkout" pode passar por dezenas de microsserviços (Gateway, Anti-fraude, Emissor do Cartão, Serviço de Notificação, Banco de Dados, etc). 
Quando um teste de API falha no CI, a mensagem "500 Internal Server Error" não diz absolutamente nada sobre **onde** o erro ocorreu. Se você, como QA/SDET, não souber usar um `X-Correlation-ID` para rastrear essa requisição nos logs da aplicação (como no Datadog, Kibana, Splunk, ou CloudWatch), você dependerá sempre de um desenvolvedor para investigar o problema. 
Automatizar testes com observabilidade em mente transforma você de "alguém que aponta bugs" para "alguém que diagnostica a causa raiz".

## 03. Pré-requisitos
- Compreensão sólida sobre requisições HTTP e Headers.
- Testes de API estruturados com Playwright (Fases anteriores).
- Conhecimento básico sobre como microsserviços se comunicam.
- Familiaridade básica com execução de testes em CI (Continuous Integration).

## 04. Conceitos
- **Observabilidade:** Capacidade de entender o estado interno de um sistema a partir de suas saídas externas (Métricas, Logs e Traces).
- **Distributed Tracing:** Técnica de rastreamento de requisições que fluem através de múltiplos microsserviços. 
- **Correlation ID (ou Trace ID):** Um identificador único gerado no ponto de entrada da requisição inicial, que é repassado (propagado) para todos os serviços subsequentes. Geralmente trafega no header `X-Correlation-ID`, `Traceparent` (W3C), ou `X-Request-Id`.
- **Logs de Teste vs Logs de Aplicação:** Logs de teste são gerados pelo Playwright (suas asserções, dados enviados/recebidos). Logs da aplicação são gerados pelo backend. O Correlation ID é a ponte entre os dois.

## 05. Explicação mastigada
Imagine que você vai ao correio despachar 3 pacotes. Para cada um, você recebe um **Código de Rastreio**. Se um pacote sumir, você não liga para o correio dizendo "meu pacote sumiu". Você diz "o pacote com rastreio XYZ sumiu".
Em APIs de pagamento, o **Correlation ID** é esse código de rastreio. 
Quando o seu teste do Playwright faz um `POST /v1/payments`, ele pode (e deve!) gerar um UUID aleatório e enviar isso num header (ex: `X-Correlation-ID: 1234-abcd`).
Se a requisição falhar (ex: erro no anti-fraude), o seu teste falha. Quando você for olhar os relatórios do Playwright, você verá: "O teste falhou. Correlation-ID usado: 1234-abcd".
Aí você vai no agregador de logs da empresa (ex: Kibana), busca por "1234-abcd" e magicamente vê toda a jornada do pagamento falho serviço a serviço, até a exata linha de código ou query no banco que quebrou.

## 06. Exemplos

### Enviando um Correlation ID Customizado
Em vez de esperar que o primeiro serviço gere o ID, nós geramos no teste para garantir que o sabemos de antemão:

```typescript
import { test, expect } from '@playwright/test';
import crypto from 'crypto';

test('Deve processar pagamento e propagar Correlation ID', async ({ request }) => {
  const correlationId = crypto.randomUUID(); // Geramos o ID no teste
  
  // Logamos o ID para fácil acesso no relatório do CI
  console.log(`[Trace] Iniciando pagamento com X-Correlation-ID: ${correlationId}`);

  const response = await request.post('https://api.sandbox.pagamentos.com/v1/charges', {
    headers: {
      'X-Correlation-ID': correlationId,
      'Authorization': 'Bearer token_aqui',
    },
    data: {
      amount: 5000,
      paymentMethod: 'PIX'
    }
  });

  // Se falhar, a asserção exibe o log, e sabemos qual ID buscar no Datadog/Kibana
  expect(response.status()).toBe(201);
});
```

## 07. Código comentado

Aqui criamos um `APIRequestContext` customizado ou fixture que injeta o `X-Correlation-ID` automaticamente em todos os testes e loga requests/responses.

```typescript
// fixtures/apiFixture.ts
import { test as base, APIRequestContext, request } from '@playwright/test';
import crypto from 'crypto';

type ApiFixtures = {
  tracedRequest: APIRequestContext;
  correlationId: string;
};

export const test = base.extend<ApiFixtures>({
  // Cria o ID unicamente por teste
  correlationId: async ({}, use) => {
    const id = crypto.randomUUID();
    await use(id);
  },
  
  // Cria um contexto de request que já inclui o header padrão
  tracedRequest: async ({ correlationId }, use) => {
    // 1. Criamos um novo contexto de request isolado
    const ctx = await request.newContext({
      baseURL: 'https://api.sandbox.pagamentos.com',
      extraHTTPHeaders: {
        'X-Correlation-ID': correlationId, // Injetado automaticamente!
        'Content-Type': 'application/json'
      }
    });
    
    // 2. Anexamos a informação no console para aparecer no Playwright Report/CI
    console.log(`[START] Test Correlation-ID: ${correlationId}`);
    
    // 3. Fornecemos o contexto para o teste
    await use(ctx);
    
    // 4. Limpeza
    await ctx.dispose();
  }
});

// tests/payment.spec.ts
// Usando a fixture customizada
// import { test } from '../fixtures/apiFixture';
// import { expect } from '@playwright/test';

// test('Estorno de pagamento', async ({ tracedRequest, correlationId }) => {
//   const response = await tracedRequest.post('/v1/refunds', {
//     data: { transactionId: 'txn_999', amount: 1000 }
//   });
//   
//   // Se o status for 500, o correlationId já estará no log do CI
//   // tornando o debug no Kibana muito mais fácil.
//   expect(response.status()).toBe(201); 
// });
```

## 08. Exercício guiado (Nível 1 - Guided)

**Objetivo:** Criar um teste que envia um `X-Request-Id`, captura ele na resposta e garante que a API está refletindo e respeitando o rastreamento.

**Passos:**
1. Crie um arquivo `observabilidade.spec.ts`.
2. Importe o módulo `crypto` do Node.js.
3. No corpo do teste, crie uma variável `traceId` usando `crypto.randomUUID()`.
4. Faça uma requisição `GET` para uma API de testes (ex: `https://httpbin.org/headers`) passando no `headers` a chave `'X-Request-Id': traceId`.
5. Capture o JSON da resposta (`await response.json()`).
6. Faça uma asserção verificando se `body.headers['X-Request-Id']` é igual ao `traceId` que você enviou.

## 09. Exercício sozinho (Nível 2 - Semi-guided)

**Objetivo:** Implementar um hook global ou custom fixture que loga detalhes apenas se a requisição falhar.

- No CI, logar TUDO (sucesso e falha) pode poluir a saída (output) do job, deixando o log com 50MB.
- Você precisa criar um teste que force um erro na API (ex: enviar um payload inválido).
- Use `test.afterEach` para verificar se o teste falhou (`testInfo.status !== testInfo.expectedStatus`).
- Se falhou, imprima um resumo amigável no console contendo:
  - O nome do teste.
  - O Correlation ID gerado.
  - Uma URL hipotética para o painel de logs (ex: `https://kibana.empresa.com/discover?query=correlation_id:"${traceId}"`).

## 10. Desafio (Nível 3 - Challenge)

**O Problema do Webhook Assíncrono:**
Em sistemas de pagamentos, muitas confirmações vêm via Webhooks (ex: Pix recebido). Você precisa testar se, ao criar um Pix, o sistema gera o webhook corretamente.
Crie um teste que:
1. Gera um `X-Correlation-ID`.
2. Faz o request de criação do Pix.
3. Você precisará simular uma consulta a um banco de dados de logs (ou usar uma API real se aplicável, como o `https://webhook.site/`) para buscar se chegou um webhook **contendo o mesmo Correlation-ID** gerado no passo 1.
4. Implemente um mecanismo de _Polling_ (tentativas repetidas com delay) para esperar até o webhook chegar ou dar timeout após 30 segundos.

## 11. Erros comuns
- **Achar que o ID é sempre devolvido no Response:** Nem toda API retorna o Correlation-ID nos headers da resposta. Por isso, gere no cliente (Playwright) e envie, assim você sabe qual é o ID independentemente do que o servidor retornar.
- **Nomes de Headers Diferentes:** Cada empresa usa um padrão. Pode ser `X-Correlation-ID`, `X-Request-ID`, `Traceparent` (padrão OpenTelemetry W3C) ou `B3-TraceId`. Pergunte aos desenvolvedores qual o padrão usado.
- **Logs demais:** Fazer `console.log(await response.json())` para toda requisição. Em um teste de sucesso com milhares de execuções no CI, isso vai estourar os limites de armazenamento de logs do pipeline.
- **Mascaramento de Dados Sensíveis:** Logar payloads inteiros sem mascarar (ofuscar) dados de cartão de crédito (PAN, CVV) ou PII (Personal Identifiable Information) como CPF. Isso é violação grave de segurança (PCI-DSS).

## 12. Debugging

### Como debuggar testes falhando no CI?
1. **Identifique a Falha:** O GitHub Actions ficou vermelho. Entre nos detalhes do Job e veja qual teste falhou (ex: `expected 200, got 500`).
2. **Localize o Trace-ID:** Vá até a linha de console do Playwright no próprio CI e copie o ID logado (`[Trace] Test Correlation-ID: 12345-abcde`).
3. **Busque nos Logs da Aplicação:** Abra a ferramenta de observabilidade do seu time (Datadog, New Relic, AWS CloudWatch, Kibana).
4. **Filtre:** Faça a query: `trace_id: "12345-abcde"` ou busque o texto livre do UUID.
5. **Analise o Fluxo:** Você verá os logs de todos os microsserviços. Exemplo:
   - `[INFO] Gateway: Recebido POST /payments (trace: 12345)`
   - `[INFO] Antifraude: Análise iniciada (trace: 12345)`
   - `[ERROR] Banco de Dados: Connection Timeout na tabela 'transactions' (trace: 12345)`
6. **Reporte:** Em vez de abrir um bug dizendo "O endpoint /payments retornou 500", abra dizendo "O endpoint /payments retornou 500 devido a um Timeout de conexão com o Banco de Dados no microserviço de Antifraude. Trace-ID de evidência: 12345-abcde". (Os devs vão chorar de emoção com um report desses).

## 13. Aplicação no projeto principal
No nosso framework Playwright de pagamentos:
1. Vamos adicionar um Custom Header global na nossa configuração (`playwright.config.ts`) ou base API controller.
2. Vamos escrever uma função de utility logger (`logger.ts`) que formata os logs pro CI de forma limpa, mostrando o Trace ID apenas quando algo importante acontece.
3. Em testes complexos que envolvem RabbitMQ/Kafka, usaremos o Trace ID gerado no teste de API para ler a fila e confirmar se a mensagem foi publicada corretamente, já que a mensagem da fila terá o mesmo Correlation-ID.

## 14. Perguntas de entrevista
1. **Se um teste de API que sempre passou começa a retornar Status 500 intermitente no Jenkins, como você investiga a causa?**
   *Resposta esperada:* Explico que não confio apenas no log do Jenkins. Eu configuro meus testes para injetar um Correlation ID nos Headers HTTP e exibir esse ID no log em caso de erro. Com esse ID, eu acesso a stack de observabilidade (ex: Kibana/Datadog) para rastrear o erro exato no backend (ex: banco indisponível, falha de downstream) e anexo esse link ao meu bug report.
2. **O que é Distributed Tracing e qual o papel do QA nisso?**
   *Resposta esperada:* É uma técnica de acompanhar a jornada completa de uma requisição em arquiteturas de microsserviços usando um ID único. O papel do QA é garantir que a estrutura de testes envie (ou recupere) esses IDs e valide se o fluxo fim-a-fim está de fato repassando o ID de contexto, garantindo a rastreabilidade e facilitando diagnósticos rápidos de bugs.
3. **Como você evita o vazamento de dados sensíveis ao registrar logs de testes de pagamento?**
   *Resposta esperada:* Implemento filtros na camada de request/response do framework que usam Regex para ofuscar (mascarar) dados como CPFs, PAN de cartões e senhas antes de dar qualquer `console.log` ou anexar arquivos de relatório no Playwright (ex: trocando o cartão para `**** **** **** 1234`).

## 15. Checklist
- [ ] Entendi a diferença entre log de teste e log de aplicação.
- [ ] Sei o que é um `X-Correlation-ID` (ou equivalente).
- [ ] Consigo injetar um UUID randômico como header usando o Playwright.
- [ ] Imprimi o ID gerado no console em caso de erro.
- [ ] Sei como usaria o ID para buscar informações nas ferramentas de log do time.
- [ ] Pratiquei a extração do header da resposta da API.

## 16. Critério para avançar
Você pode avançar para a próxima fase quando seu framework for capaz de injetar de forma transparente (ou via helper function explícita) um Correlation ID por teste, logá-lo com clareza no terminal apenas se o teste falhar, sem poluir a execução se tudo passar com sucesso. O conhecimento daqui separa QAs juniores dos sêniores!
