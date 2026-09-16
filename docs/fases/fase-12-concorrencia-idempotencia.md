# Fase 12: Concorrência + Idempotência

## 01. O que você vai aprender
- O que é Idempotência e por que é um conceito obrigatório em APIs de pagamento.
- Como o cabeçalho `Idempotency-Key` funciona na prática para evitar transações duplicadas.
- Como simular condições de corrida (*Race Conditions*) enviando múltiplas requisições simultâneas usando o Playwright.
- Como testar e validar se o sistema impede cobranças duplicadas (*Double-charges*).
- Estratégias para estruturar testes de concorrência com a função `Promise.all()` do JavaScript/TypeScript.

## 02. Por que isso importa para um QA
No ecossistema financeiro, o pior pesadelo de uma empresa é cobrar o cliente duas vezes pela mesma compra ou debitar um Pix em duplicidade. Isso gera atritos severos com clientes, possíveis processos legais, acionamento do BACEN, perdas com estornos (*chargebacks*) e destruição irreversível da confiança na marca.
Como QA de pagamentos (SDET), você não pode limitar seus testes ao "caminho feliz" onde uma requisição é enviada de forma controlada por vez. Em ambientes de produção reais, instabilidades de rede (3G/4G/5G oscilando), falhas de retentativas automáticas no frontend ou clientes impacientes apertando o botão "Pagar" várias vezes geram disparos de requisições idênticas quase no mesmo milissegundo. Garantir que a API possui travas e lida corretamente com a concorrência e a idempotência é a diferença entre manter um sistema maduro e arcar com um prejuízo milionário.

## 03. Pré-requisitos
- Compreensão sólida e uso prático no envio de requisições HTTP REST (`POST`, `GET`, etc.).
- Conhecimento em configuração e envio de cabeçalhos (*Headers*) na APIRequestContext do Playwright.
- Domínio do funcionamento de Promises e assincronicidade no JavaScript/TypeScript (especialmente a manipulação do `Promise.all`).
- (Recomendado) Conhecimento básico sobre concorrência, travas de banco de dados e transações ACID.

## 04. Conceitos
- **Idempotência**: Em matemática e ciência da computação, é a propriedade de certas operações poderem ser aplicadas várias vezes sem que o resultado mude após a primeira aplicação. Num contexto de pagamentos, enviar a mesma cobrança com a mesma identificação de intenção uma ou mil vezes deve resultar em **apenas uma transação debitada e persistida**.
- **Idempotency-Key**: Um cabeçalho HTTP (geralmente contendo um identificador único, como UUIDv4) gerado por quem consome a API (um aplicativo frontend, por exemplo) para carimbar a singularidade daquela intenção específica de compra.
- **Race Condition (Condição de Corrida)**: Uma anomalia onde o comportamento de um sistema ou aplicação depende de sequências ou tempo incontroláveis de processamentos (ex: duas requisições idênticas alcançam os servidores no mesmo instante, antes que o banco de dados seja atualizado a tempo para rejeitar a segunda).
- **Double-Charge**: A consequência financeira catastrófica da falha do sistema na prevenção de concorrência e idempotência. É a cobrança duplicada.

## 05. Explicação mastigada
Imagine a seguinte cena: você está finalizando o pagamento de uma compra usando o saldo da carteira virtual em uma rede de celular muito lenta. O aplicativo tenta processar, fica com a tela congelada e, em meio ao nervosismo, você aperta o botão de "Confirmar Compra" umas 5 vezes seguidas.
Se a API financeira não for protegida (sem tratamento de concorrência e idempotência), ela processará as 5 requisições de forma independente e abaterá o saldo da sua carteira 5 vezes consecutivas!
Caso o sistema seja robusto, assim que a tela de confirmação abrir, o app irá gerar um ID exclusivo (sua `Idempotency-Key`). Todas as 5 requisições seguirão com a *mesma chave* no cabeçalho.
Quando o servidor receber a requisição número 1, ele inicia a cobrança e sinaliza internamente (através de um lock no banco ou em cache) que aquela chave já está em progresso. Um milissegundo depois, as requisições de 2 a 5 chegam no servidor. Ele confere e entende: "Eu já conheço essa Idempotency-Key e já estou tratando! Ignorarei essas chamadas e entregarei a elas o mesmo resultado da primeira". 
Com o Playwright, somos capazes de usar a mágica do `Promise.all()` para "atirar" contra o servidor todas as requisições ao mesmo tempo, averiguando se o backend de fato segura o tranco.

## 06. Exemplos
**Cenário Real de Integração via API (Padrão de Gateways modernos):**
- **Endpoint e Verbo HTTP:** `POST /v1/charges`
- **Cabeçalhos de controle:** `Idempotency-Key: e8a3d13d-51a4-4f05-8e2b-f350c30a8c25`
- **Comportamento Esperado na API:**
  - Requisição A: Realiza a cobrança no banco -> Retorna Status `201 Created` e gera um ID de Transação (ex: `txn_001`).
  - Requisição B (concorrente/re-tentativa com a mesma chave): O sistema bloqueia a dupla cobrança -> Pode retornar `409 Conflict` (explicando que é duplicada) ou responder o mesmo `201 Created` espelhando a resposta da original.
  - No banco de dados, se consultado o saldo do cliente ou a tabela de transações, veremos exatamente e apenas um débito gerado.

## 07. Código comentado
```typescript
import { test, expect } from '@playwright/test';
import { v4 as uuidv4 } from 'uuid'; // Instale essa biblioteca no seu projeto para gerar IDs únicos e reais

test.describe('Testes de Prevenção de Concorrência e Idempotência', () => {

  test('Deve processar e cobrar apenas 1 pagamento ao enviar múltiplas requisições com a mesma Idempotency-Key', async ({ request }) => {
    // 1. O cliente cria e atrela uma "Idempotency-Key" a essa intenção de compra específica
    const idempotencyKey = uuidv4();
    
    // 2. Preparamos o conteúdo do pagamento com o cartão
    const payloadPagamento = {
      amount: 15000, // R$ 150,00 representados em centavos
      currency: 'BRL',
      paymentMethod: 'credit_card',
      cardToken: 'tok_visa_valid'
    };

    // 3. Montamos um array para receber promessas de requisições que NÃO devem ser resolvidas imediatamente
    const NUMERO_REQUISICOES = 5;
    const promessasDeRequisicao = [];

    // O "for" não usa "await" propositalmente! Queremos carregar a "arma" para atirar tudo junto!
    for (let i = 0; i < NUMERO_REQUISICOES; i++) {
      promessasDeRequisicao.push(
        request.post('/v1/payments', {
          data: payloadPagamento,
          headers: {
            'Idempotency-Key': idempotencyKey, // Todas carregam a mesma chave
            'Authorization': 'Bearer test_token_secret_123'
          }
        })
      );
    }

    // 4. Disparamos todas as chamadas de uma única vez. 
    // É isso que simula o estresse de concorrência ou um "dedo nervoso" do cliente final.
    const respostas = await Promise.all(promessasDeRequisicao);

    // 5. Analisamos os resultados que o Backend entregou.
    // Dependendo do padrão implementado no backend, os bloqueios de concorrência podem vir
    // como erro (Ex: 409 Conflict / 422 Unprocessable Entity) ou, mais comum em Idempotência "real",
    // todas devem voltar como 201 Created apontando para o mesmíssimo objeto da primeira.
    // Assumiremos aqui um modelo em que 1 passa limpa e 4 retornam "409 Conflict" (bloqueadas).
    
    const statusCodes = respostas.map(response => response.status());
    
    const criados = statusCodes.filter(status => status === 201);
    const conflitados = statusCodes.filter(status => status === 409);

    // Validações explícitas de que o limite funcionou perfeitamente
    expect(criados.length, 'Apenas 1 processamento deve acontecer, protegendo de cobrança duplicada').toBe(1);
    expect(conflitados.length, 'As outras 4 tentativas da race-condition devem causar conflito no Lock da API').toBe(4);

    // 6. (Recomendação Avançada) Validar na fonte da verdade: O Banco de Dados.
    // É essencial atestar que mesmo com respostas instáveis na web, a conta matemática lá no banco fecha em 1.
    // const transacoesLimpasNoBD = await bancoDeDados.query(`SELECT id FROM payments WHERE idempotency_key = '${idempotencyKey}'`);
    // expect(transacoesLimpasNoBD.length).toBe(1);
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo:** Disparar 3 requisições Pix simultâneas simulando um erro do aplicativo sem duplo repasse.
**Instruções passo a passo:**
1. Crie um novo arquivo de testes `pix-concurrency.spec.ts`.
2. Importe o `uuid` e gere uma chave.
3. Defina um payload de transferência Pix (ex: `amount: 100`, `chave_destino: email@empresa.com`).
4. Inicialize um array vazio e use um loop (`for`) para dar 3 `push()` no array contendo as requisições `request.post` para `/v1/pix` **sem usar await** interno. Lembre-se de passar o header de idempotência.
5. Embaixo do loop, utilize o `Promise.all(suaVariavelDeArray)` aguardando (`await`) seu término e capture as respostas.
6. Leia todos os *status codes* retornados no array final e monte as asserções de modo que apenas uma requisição saia vitoriosa e evite que a sua conta estoure.
7. Rode no terminal com `npx playwright test`.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo:** Validar o mecanismo de trava (*lock*) do sistema sem a ajuda do `Idempotency-Key`.
**Cenário de Teste:** Vamos testar a API de Reembolsos de Cartão. Nela, o usuário requisita 5 cancelamentos para o **mesmo** número de transação (`transaction_id`) de forma simultânea. Neste endpoint, o desenvolvedor informou que não há necessidade de envio da chave, pois o sistema deveria travar na raiz pelo próprio identificador de quem vai ser estornado.
**Tarefa:** Programe um array de concorrências para o endpoint `POST /v1/refunds`. Envie no corpo (body) algo como `{ "transaction_id": "txn_889922" }` cinco vezes ao mesmo tempo. 
Verifique se a API processou e devolveu um código de sucesso (ex: `201`) estornando o cartão **apenas na primeira requisição**. As requisições simultâneas devem obrigatoriamente ser barradas (retornando algo como erro de "Já estornado" com status 400 ou 422). 

## 10. Desafio (Nível 3 - Challenge)
**Objetivo:** Testar a integridade robusta da memória de idempotência e validar se ela expõe falhas de mutação no payload (uma exigência de alto escalão na Stripe e no padrão global).
**Siga o roteiro:**
1. Execute um `request.post` singular para `/v1/payments` informando uma `Idempotency-Key` recém-criada, gerando um pagamento de **R$ 200,00** e espere que ele retorne um `201 Created`. Salve internamente no teste o ID retornado.
2. Aguarde 2 segundos usando um artificio assíncrono (ou no Playwright `page.waitForTimeout` caso esteja com uma tela instanciada).
3. Após essa pausa, envie uma *segunda requisição exatamente idêntica* (mesmo body, mesma chave). Valide que a API seja tolerante (retornando `201 Created`) mas atente-se: **O Body e o identificador do pagamento devem ser 100% iguais à primeira resposta**. Ela não pode gerar uma segunda venda, deve ser um reflexo em memória da intenção que você concluiu primeiro!
4. Para o "Grand Finale", dispare uma terceira requisição usando a **mesma chave** antiga de novo, mas modifique o valor que antes era R$ 200,00 para **R$ 300,00**. A API deve detectar o perigo, bloquear a requisição e retornar `400 Bad Request` ou similar, avisando enfaticamente que aquela chave de idempotência já foi utilizada outrora para outra intenção de pagamento. Você não pode reutilizá-la para cobrar valores diferentes!

## 11. Erros comuns
- **Achar que `awaits` sequenciais validam condição de corrida:** Muita gente cria testes lentos fazendo um `await request.post()` seguido por um outro na linha inferior. Eles testarão o caminho feliz no máximo, nunca a concorrência verdadeira da rede. A corrida se dá quando múltiplas chamadas ativam o roteador de requests para chegar ao backend ao mesmo tempo de mãos dadas! Sem o `Promise.all` em Playwright, você não simula esse estresse.
- **Deixar de inspecionar a fonte geradora no Banco de Dados:** Você se limita a ver a API jogar de volta "409 Conflict" e julga que passou. Mas e se nos bastidores o motor contábil salvou o dinheiro duplo em tabelas e os *logs* e não completou o *rollback* transacional? A validação direta no SQL via ferramentas conectadas garante blindagem.
- **Utilizar strings codificadas na mão para chaves únicas:** Em um teste contínuo (CI/CD), escrever na mão a constante `const key = 'minha-chave-unica'` funcionará na sua primeira corrida e falhará permanentemente de amanhã em diante, já que a mesma chave estará gasta para sempre no BD central. Adote os UUIDs dinâmicos em `beforeEach` ou início de testes.

## 12. Debugging
- **"O meu teste está instável (Flaky Test). Ele roda liso no meu computador, mas 50% das vezes reprova na nuvem (GitHub Actions / GitLab CI)."**
Esse é o problema mais natural de quem automatiza concorrência em CI. Pode ser que a rede do pipeline ou a latência local afete os momentos de disparo, de forma que as 5 promessas não batam no servidor tão unidas temporalmente. Quando elas chegam em fatias ligeiramente descompassadas, a API pode travar mais requisições pelas restrições normais antes da *Race Condition* de fato existir. Um projeto de Engenharia maduro entende que um sistema Idempotente e robusto deve resistir com resultados padronizados se a requisição chegar junto no milissegundo inicial ou se tiver frações de atraso. Avalie a flexibilidade dos retornos HTTP esperados no arranjo do seu teste (aceitando certas combinações de status).
- Caso o resultado de respostas quebre e você deseje saber o "por que" de os códigos diferirem do esperado, abra as portas de diagnóstico da execução mapeando e exibindo no console cada uma:
```typescript
  respostas.forEach(async (r, i) => console.log(`Disparo ${i} - Status Code: ${r.status()} \n Corpo da Resposta: ${await r.text()}`));
```

## 13. Aplicação no projeto principal
Na simulação de API Fintech do curso, essa 12ª Fase nos fornecerá toda a segurança contábil ao implementarmos os serviços de Transferências e Emissão de Cartão. Quando rodarmos esse conjunto na nossa plataforma de CI (integração contínua), esse teste terá a prioridade máxima e funcionará como nosso alarme patrimonial. Ele será capaz de acusar instantaneamente qualquer novo código subido pelos desenvolvedores do sistema que acabe esbarrando na supressão da checagem de concorrência ou que remova um bloqueio (*Redis Lock*/*Database Constraint*) necessário, salvando vidas de operações inteiras que de outra forma seriam um caos financeiro ao entrar em ambiente produtivo.

## 14. Perguntas de entrevista
1. **Poderia definir o que é Idempotência numa API Web e nomear quais métodos (Verbos HTTP) já contam naturalmente com essa característica em seu padrão REST?**
   *Resposta Esperada:* A idempotência atesta que múltiplas execuções com os mesmos parâmetros gerarão o mesmo estado no servidor além da primeira vez. Em REST, o método `PUT` possui essa natureza nativa (pois atualizar o endereço do João de 'X' para 'Y' vinte vezes seguidas resultará no exato mesmo endereço 'Y'), bem como `DELETE` (pois um item apagado continua apagado na base se tentarmos de novo). O `POST` não é idempotente; é feito para criar um recurso repetidas vezes, e é justamente por isso que precisamos domá-lo num cabeçalho como a `Idempotency-Key` no mercado financeiro.
2. **Como a sua automação identificaria ou provaria o perigo de "Double-charge" provocado por uma instabilidade do site para a API de Gateway do lojista?**
   *Resposta Esperada:* Eu montaria um cenário usando a biblioteca Playwright disparando chamadas agrupadas através da estrutura de `Promise.all` em requisições de pagamento simultâneas em série. Enviaria um conjunto de disparos com ID repetido, conferindo após as resoluções da *Promise* se apenas o primeiro retornou *Status Code* `201` ou `200`, se os demais falharam (ou retornaram a mesma foto do que foi efetivado antes) e completaria garantindo que no Banco de Dados a transação debitada totalize apenas um registro contábil.
3. **Se um microserviço tentar reutilizar um `Idempotency-Key` em que o pagamento original foi de R$ 500 e enviar desta vez com valor de R$ 900, o que você espera receber da API, e o que ela deve garantir?**
   *Resposta Esperada:* Minha automação espera receber uma clara falha e não uma nova cobrança de R$ 900,00 e tão pouco aprovar os R$ 500,00 passados daquele ID. O servidor precisa estar programado para inspecionar que a assinatura/hash da intenção nova corrompeu o *payload* (corpo) atrelado à chave anterior e abortar imediatamente com algo parecido com `400 Bad Request`, atestando mau uso da estrutura de integridade ou possível adulteração de dados.

## 15. Checklist
- [ ] Consegui absorver inteiramente o raciocínio preventivo de uma `Idempotency-Key`.
- [ ] Tenho dimensão da gravidade que as *Race Conditions* e *Double-charges* provocam em plataformas financeiras e de pagamentos reais.
- [ ] Sei implementar, programar e validar uma array de assincronismos via `Promise.all()` usando o Playwright e TypeScript para testar requisições sobrecarregadas.
- [ ] Compreendi que a validação vai além da resposta estática de erro de conflito HTTP, englobando a garantia que o registro não mutou e nem replicou nos bancos de dados de contabilidade ou saldo do usuário.
- [ ] Entendi a diferença das repostas de um Gateway de mercado: as tolerantes (que respondem com a mesma carga gerada do sucesso na cache) das restritivas (que disparam erro acusando lock em concorrência).

## 16. Critério para avançar
Você está totalmente capacitado a prosseguir para a nova fase do curso assim que sua suíte de testes com a estrutura da `Promise.all()` consiga disparar "à queima-roupa" ao menos cinco intenções idênticas, comprovando no terminal e com suas lógicas de asserção (expectativas) que de fato apenas uma chamada original vingou positivamente contra a barreira e evitou cobranças repetitivas do cliente-teste. Quando o seu teste espelhar com exatidão o risco estressante do mundo real numa rede bancária, o seu aprendizado dessa etapa terá sido efetivado com sucesso!
