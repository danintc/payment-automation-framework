# Fase 13: Resiliência + Toxiproxy

## 01. O que você vai aprender
Nesta fase, mergulharemos no mundo da Engenharia do Caos (Chaos Engineering) voltada para QA. Você vai aprender a testar a resiliência de integrações de pagamento simulando cenários adversos de rede, como latência alta, queda de conexão e pacotes corrompidos, usando o Toxiproxy. Também vamos validar se a nossa aplicação e nossos testes lidam corretamente com *retries* e *timeouts*.

## 02. Por que isso importa para um QA
Em sistemas de pagamento, as coisas vão dar errado: bancos ficam lentos, APIs de adquirentes caem, e a rede do usuário falha bem na hora do checkout. Se o nosso sistema não for resiliente (não souber lidar com falhas graciosamente), podemos ter dupla cobrança, pedidos travados ou perda de dinheiro. Testar o "caminho feliz" é fácil; o diferencial de um SDET é garantir que o sistema sobreviva quando a infraestrutura pega fogo.

## 03. Pré-requisitos
- Compreensão sobre chamadas assíncronas no Playwright (Fases anteriores).
- Familiaridade com Docker (para rodar o Toxiproxy).
- Entendimento de configurações de `timeout` no Playwright.

## 04. Conceitos
- **Chaos Engineering**: A prática de introduzir falhas intencionalmente em um sistema para provar que ele consegue resistir a condições adversas em produção.
- **Toxiproxy**: Um proxy de rede criado pela Shopify para simular condições de rede instáveis. Você o coloca no meio da comunicação (Aplicação -> Toxiproxy -> Banco/API Externa) e aplica "tóxicos" (latência, timeout, etc.).
- **Tóxicos (Toxics)**: As regras injetadas pelo Toxiproxy (ex: `latency`, `bandwidth`, `timeout`, `slicer`).
- **Retries**: Mecanismo onde um sistema tenta novamente uma operação que falhou (ex: reconectar a uma API).
- **Timeouts**: Tempo máximo que um sistema espera por uma resposta antes de abortar a operação.
- **Idempotência**: Garantia de que uma operação, mesmo que repetida, terá o mesmo resultado (essencial quando ocorrem retries).

## 05. Explicação mastigada
Imagine o Toxiproxy como um "carteiro malvado". Você pede para ele entregar uma carta (request) para a API do Gateway de Pagamento, mas você o instrui a: "atrase essa carta em 5 segundos" ou "jogue a resposta fora".
Em vez de a nossa aplicação conectar direto em `api.gateway.com`, ela conecta no Toxiproxy (`localhost:8474`). O Toxiproxy, por sua vez, redireciona o tráfego para `api.gateway.com`. Através de uma API do próprio Toxiproxy, nós (os QAs, em tempo de teste) aplicamos venenos (tóxicos) nessa rota, simulando latência ou queda. Assim, podemos testar se o sistema principal tem o `timeout` correto ou se tenta processar o pagamento de novo sem duplicar a cobrança.

## 06. Exemplos
**Simulando um Timeout de Gateway:**
Se a API de emissão de Pix do banco demorar 30 segundos, nosso serviço não deve travar; ele deve dar timeout aos 10 segundos, salvar o status como `PENDING_RETRY` e tentar novamente depois.

**Simulando Queda de Rede durante Webhook:**
Quando a adquirente envia o webhook de `PAYMENT_APPROVED`, mas nossa rede sofre interrupção, nosso servidor não envia o `200 OK`. A adquirente deve enviar o webhook novamente após alguns minutos (retry do parceiro).

## 07. Código comentado

Primeiro, instalamos a lib do Toxiproxy para Node:
```bash
npm install -D toxiproxy-node-client
```

Exemplo de teste usando Toxiproxy no Playwright:

```typescript
import { test, expect } from '@playwright/test';
import { Toxiproxy, Toxic } from 'toxiproxy-node-client';

// O Toxiproxy já deve estar rodando (via docker) no localhost:8474
const toxiproxy = new Toxiproxy('http://localhost:8474');

test.describe('Testes de Resiliência - Gateway de Pagamento', () => {
  let gatewayProxy;

  test.beforeAll(async () => {
    // Cria um proxy no Toxiproxy. 
    // Listen: porta que nossa aplicação vai chamar
    // Upstream: o gateway real (ou mock do gateway)
    gatewayProxy = await toxiproxy.createProxy({
      name: 'payment-gateway',
      listen: 'localhost:8080',
      upstream: 'sandbox.paymentgateway.com:443'
    });
  });

  test.afterAll(async () => {
    await gatewayProxy.remove();
  });

  test.afterEach(async () => {
    // Removemos os tóxicos após cada teste para deixar a rede limpa
    const proxy = await toxiproxy.get('payment-gateway');
    await proxy.refreshToxics(); // Sincroniza estado
    for (const toxic of proxy.toxics) {
      await toxic.remove();
    }
  });

  test('Deve retornar status 504 e salvar como falha quando o gateway estiver com alta latência', async ({ request }) => {
    // 1. Injetamos uma latência de 10 segundos no proxy
    const proxy = await toxiproxy.get('payment-gateway');
    await proxy.addToxic(new Toxic(proxy, {
      type: 'latency',
      attributes: { latency: 10000, jitter: 1000 } // Atrasa em 10s ± 1s
    }));

    // 2. Fazemos o request para a nossa própria API que consome o proxy
    // Nossa API deve ter um timeout configurado menor que 10s (ex: 5s)
    const response = await request.post('/api/checkout', {
      data: {
        userId: '123',
        amount: 50.00,
        paymentMethod: 'CREDIT_CARD'
      }
    });

    // 3. Validamos que nossa API não ficou presa e retornou erro gracefully
    expect(response.status()).toBe(504); // Gateway Timeout
    const body = await response.json();
    expect(body.message).toBe('Pagamento pendente devido a instabilidade externa. O processo continuará em background.');
  });
});
```
*(Nota: O exemplo acima assume que o serviço em teste está configurado para apontar para `localhost:8080` em vez de `sandbox.paymentgateway.com` no ambiente de testes).*

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo**: Criar um proxy que corta a conexão (`reset_peer`) no meio da transação.

1. Suba o Toxiproxy via Docker: `docker run --rm -p 8474:8474 -p 8080:8080 ghcr.io/shopify/toxiproxy`.
2. No seu arquivo de testes, crie o setup do Toxiproxy conectando a um mock de API (pode ser o wiremock ou uma API pública falsa).
3. Escreva um teste que cria um tóxico do tipo `reset_peer`. (Este tóxico fecha a conexão TCP subitamente).
4. Faça uma requisição para a sua API e valide que a resposta lidou bem com o erro de rede (retornando HTTP 502 Bad Gateway ou acionando uma retentativa automática).

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo**: Validar retries (tentativas automáticas) do seu sistema.
Seu sistema foi configurado para tentar até 3 vezes caso receba um erro de rede.
- Use o Toxiproxy para adicionar um tóxico de `limit_data` ou `timeout`.
- Mas configure o tóxico para acontecer apenas em um *stream* específico ou desative o tóxico no meio do teste usando Playwright, simulando que a rede "voltou".
- Valide no banco de dados da sua aplicação que um registro de tentativa falha foi criado, mas a segunda tentativa obteve sucesso.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo**: Resiliência no disparo de Webhooks com Toxiproxy.
Crie um cenário ponta-a-ponta (E2E) em que:
1. Um parceiro solicita um pagamento Pix.
2. Seu sistema agenda um webhook para notificar o parceiro quando o Pix for pago.
3. Você cria o proxy do Toxiproxy virado para o endpoint do parceiro.
4. Adiciona um tóxico de *latency* absurdo (60s).
5. Seu sistema tenta disparar o webhook, falha por timeout e joga a mensagem para uma DLQ (Dead Letter Queue) do RabbitMQ ou SQS.
6. Valide a presença da mensagem na DLQ usando a API/SDK do Message Broker no Playwright.

## 11. Erros comuns
- **Esquecer de remover os tóxicos após o teste**: Se você não limpar os tóxicos no `afterEach`, os testes subsequentes vão falhar por lentidão ou queda, causando falsos positivos.
- **Configuração de portas incorreta**: O Toxiproxy precisa de uma porta para escutar (listen). Certifique-se de que a aplicação em teste está apontando para essa porta do Toxiproxy, e não para o endpoint real.
- **Conflito de portas**: Tentar rodar o Toxiproxy em uma porta que já está em uso na sua máquina.

## 12. Debugging
- Use a interface de linha de comando do Toxiproxy (CLI) ou as requisições HTTP na porta 8474 para listar as proxies ativas e os tóxicos rodando. 
- Se a aplicação não estiver sofrendo a latência, verifique se as variáveis de ambiente (ex: `GATEWAY_URL`) foram injetadas corretamente no seu sistema de testes apontando para o proxy em vez do host direto.

## 13. Aplicação no projeto principal
Na arquitetura do nosso sistema de pagamentos, iremos inserir o Toxiproxy entre o nosso "Core de Pagamentos" e a "API do Adquirente Fictício" no `docker-compose.test.yml`. Todos os testes e2e de estresse passarão por esse proxy, garantindo que timeouts no emissor do cartão não derrubem nossa API.

## 14. Perguntas de entrevista
- **O que é Chaos Engineering e como um QA pode aplicá-lo em testes de API?**
  *Resposta:* É a prática de injetar falhas ativamente (como latência, quedas de banco, falhas de rede) para garantir que a aplicação saiba lidar com essas situações em produção. QAs podem automatizar esses testes em CI/CD usando ferramentas como Toxiproxy ou Chaos Mesh para validar retries, circuit breakers e timeouts.
- **Como você testa uma funcionalidade que depende de retries assíncronos?**
  *Resposta:* Eu posso simular a falha injetando lentidão no serviço alvo, usar o Playwright para observar a resposta (esperando um status de processamento de background) e usar testes que consultam o banco de dados ou mensageria repetidamente (polling) até que a tentativa seguinte tenha sucesso ou seja levada para uma DLQ.

## 15. Checklist
- [ ] Entendi o conceito de Engenharia do Caos e Toxiproxy.
- [ ] Configurei o Toxiproxy no meu ambiente local/docker.
- [ ] Escrevi testes adicionando tóxicos de latência (`latency`).
- [ ] Validei os comportamentos de timeout e retry.
- [ ] Limpei os tóxicos no gancho `afterEach` (teardown).

## 16. Critério para avançar
Você pode seguir para a próxima fase quando seu projeto rodar testes de ponta a ponta falhando graciosamente em caso de queda do gateway, provando que não há "transações fantasmas" perdidas sem logging.
