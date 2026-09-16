# Fase 14: Segurança de APIs

## 01. O que você vai aprender
- Os principais riscos de segurança em APIs baseados no OWASP API Security Top 10.
- Como identificar e explorar (de forma ética e para testes) vulnerabilidades como BOLA (IDOR), Broken Authentication e Mass Assignment.
- Como automatizar testes de segurança em APIs de pagamento utilizando Playwright e TypeScript.
- Melhores práticas para validar cabeçalhos de segurança e tokens JWT.

## 02. Por que isso importa para um QA
Em sistemas de pagamento, uma falha de segurança pode resultar em perdas financeiras milionárias, multas regulatórias e destruição da reputação da empresa. Como SDET, você não é apenas responsável por garantir que o sistema "funciona", mas também por garantir que ele é resiliente contra ataques. Testar segurança não é exclusividade do time de InfoSec; automatizar verificações básicas de segurança no seu pipeline (Shift-Left Security) previne que vulnerabilidades críticas cheguem em produção.

## 03. Pré-requisitos
- Conhecimento sólido em requisições HTTP (GET, POST, PUT, DELETE) e Status Codes.
- Compreensão de como a autenticação via JWT (JSON Web Tokens) funciona.
- Familiaridade com o Playwright e TypeScript.
- Entendimento básico do modelo de dados de um sistema de pagamentos (Usuários, Contas, Transações).

## 04. Conceitos
- **OWASP API Security Top 10**: Uma lista das vulnerabilidades mais críticas em APIs.
- **BOLA (Broken Object Level Authorization) / IDOR (Insecure Direct Object Reference)**: Ocorre quando uma API expõe um endpoint que manipula um objeto através de seu ID, e não valida se o usuário autenticado tem permissão para acessar aquele objeto específico. Ex: Usuário A acessa a fatura do Usuário B mudando o ID na URL.
- **Broken Authentication**: Falhas no mecanismo de autenticação, permitindo que atacantes assumam a identidade de outros usuários (ex: tokens JWT não expirando, senhas fracas, falta de rate limiting no login).
- **Mass Assignment**: Ocorre quando a API permite que o cliente atualize propriedades de um objeto que não deveriam ser modificadas pelo usuário. Ex: Mudar o campo `isAdmin` para `true` ou alterar o `status` de uma transação de `pending` para `approved` via payload do POST/PUT.

## 05. Explicação mastigada
Imagine um banco. O **Broken Authentication** é como se a porta do cofre aceitasse qualquer chave parecida com a original, ou se o segurança não verificasse a validade do seu crachá. O **BOLA (IDOR)** é como se, após entrar no banco com sua chave do cofre 10, você simplesmente tentasse abrir o cofre 11 com a mesma chave e a porta se abrisse, só porque você pediu para ver o cofre 11. O **Mass Assignment** é como preencher um formulário de depósito onde você mesmo escreve seu "saldo final desejado" em vez de apenas o valor do depósito, e o banco aceita essa informação cega.

Em nossos testes com Playwright, vamos simular esses ataques:
1. **BOLA**: Fazer login como Usuário A (comprador) e tentar ler dados da transação do Usuário B.
2. **Broken Auth**: Tentar usar um token expirado, malformado ou sem assinatura para fazer uma transferência.
3. **Mass Assignment**: Enviar campos extras não documentados no JSON (como `status: "PAID"`) durante a criação de um pagamento e verificar se a API rejeita ou ignora adequadamente.

## 06. Exemplos

- **Cenário de BOLA**:
  - `GET /api/v1/payments/999` (ID de outro usuário).
  - Esperado: `403 Forbidden` ou `404 Not Found`.
  - Atual (vulnerável): `200 OK` retornando dados do cartão do outro usuário.

- **Cenário de Mass Assignment**:
  - `POST /api/v1/users` com payload `{ "username": "teste", "role": "admin" }`.
  - Esperado: O usuário é criado, mas a API ignora o campo `role`, definindo como `user`.
  - Atual (vulnerável): O usuário é criado com privilégios de `admin`.

## 07. Código comentado

```typescript
import { test, expect, request } from '@playwright/test';

test.describe('Testes de Segurança - OWASP API Top 10', () => {
  let userAToken: string;
  let userBToken: string;
  let userATransactionId: string;

  test.beforeAll(async () => {
    const apiContext = await request.newContext();
    
    // Setup: Login Usuário A e Usuário B
    const loginA = await apiContext.post('/api/auth/login', { data: { email: 'userA@teste.com', password: 'passwordA' } });
    userAToken = (await loginA.json()).token;

    const loginB = await apiContext.post('/api/auth/login', { data: { email: 'userB@teste.com', password: 'passwordB' } });
    userBToken = (await loginB.json()).token;

    // Setup: Criar transação para o Usuário A
    const txResponse = await apiContext.post('/api/payments', {
      headers: { Authorization: `Bearer ${userAToken}` },
      data: { amount: 100, receiver: 'loja123' }
    });
    userATransactionId = (await txResponse.json()).id;
  });

  test('Deve prevenir BOLA (IDOR) ao tentar acessar transação de outro usuário', async ({ request }) => {
    // Ação: Usuário B tenta acessar a transação do Usuário A usando seu próprio token
    const response = await request.get(`/api/payments/${userATransactionId}`, {
      headers: { Authorization: `Bearer ${userBToken}` }
    });

    // Validação: A API deve bloquear o acesso (403 ou 404 para não vazar a existência do ID)
    expect([403, 404]).toContain(response.status());
  });

  test('Deve prevenir Broken Authentication rejeitando tokens inválidos/forjados', async ({ request }) => {
    // Ação: Envia um token forjado (modificando o payload sem assinar)
    const forgedToken = userAToken.substring(0, userAToken.length - 5) + "12345";
    
    const response = await request.post('/api/payments/withdraw', {
      headers: { Authorization: `Bearer ${forgedToken}` },
      data: { amount: 5000 }
    });

    // Validação: A API deve perceber que a assinatura é inválida
    expect(response.status()).toBe(401);
  });

  test('Deve prevenir Mass Assignment na criação de pagamento', async ({ request }) => {
    // Ação: Tenta forçar o status de um pagamento na criação
    const response = await request.post('/api/payments', {
      headers: { Authorization: `Bearer ${userAToken}` },
      data: { 
        amount: 50, 
        receiver: 'loja123',
        status: 'COMPLETED', // Campo injetado de forma maliciosa
        isRefunded: true     // Campo injetado de forma maliciosa
      }
    });

    // Verifica se a requisição passou
    expect(response.status()).toBe(201);
    const body = await response.json();

    // Validação de Segurança: A API deve ignorar os campos injetados e assumir os valores default
    expect(body.status).toBe('PENDING'); // Não deve ser COMPLETED
    expect(body.isRefunded).toBe(false); // Não deve ser true
  });
});
```

## 08. Exercício guiado (Nível 1 - Guided)
**Objetivo**: Automatizar um teste de BOLA para a exclusão de um cartão de crédito.
1. Crie dois usuários no banco ou via API (User1 e User2).
2. Adicione um cartão de crédito no perfil do User1 e pegue o `cardId`.
3. Com o token do User2, faça um `DELETE /api/users/cards/${cardId}`.
4. Faça um `expect(response.status()).toBe(403)`.
5. Verifique (usando o token do User1) se o cartão ainda existe (fazendo um `GET`).

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Objetivo**: Testar *Broken Authentication* (Rate Limiting).
APIs de pagamento devem proteger a rota de login contra *Brute Force*.
- Crie um teste que faça um loop de 20 requisições POST para `/api/auth/login` com uma senha incorreta.
- Valide se a API eventualmente começa a retornar `429 Too Many Requests` ou se bloqueia a conta temporariamente.
- *Dica*: Use um `for` loop, guarde as respostas em um array e verifique se pelo menos uma contém o status 429.

## 10. Desafio (Nível 3 - Challenge)
**Objetivo**: Explorar Mass Assignment em uma atualização de perfil (PUT).
1. Leia a documentação da sua API fictícia de pagamentos para entender os campos do usuário.
2. Identifique campos sensíveis no modelo de `User` (ex: `balance`, `isAdmin`, `kycVerified`).
3. Tente fazer um `PUT /api/users/me` passando um JSON onde você injeta um aumento no `balance` (saldo) e define `kycVerified: true`.
4. Valide se a API filtra esses campos (seu saldo não deve aumentar magicamente e o KYC não deve pular para verificado).

## 11. Erros comuns
- **Achar que 401 e 403 são a mesma coisa**: 401 = Quem é você? (Token inválido/ausente). 403 = Eu sei quem você é, mas você não pode fazer isso (Permissão insuficiente/BOLA).
- **Testar segurança apenas com caminhos felizes**: Muitos QAs verificam apenas se o token válido funciona, mas esquecem de testar tokens expirados, alterados ou tokens de *outros* usuários da mesma role.
- **Deixar lixo no banco**: Testes de segurança geralmente criam muitos dados anômalos. Lembre-se de ter um bloco `afterAll` para limpar tudo.

## 12. Debugging
- **O teste de BOLA está passando e retornando 200 OK! E agora?** Parabéns, você encontrou uma falha grave! O debugging neste caso não é do teste, mas da API. Crie um bug ticket com a severidade máxima, anexe o payload do Playwright e os logs mostrando que o Token B acessou os dados do ID A.
- Se você tomar erro de CORS nos testes locais ao injetar headers esquisitos, configure seu backend de teste para aceitar requisições da sua máquina ou utilize o context options do Playwright para ignorar HTTPS/CORS.

## 13. Aplicação no projeto principal
Em nosso projeto de API de Gateway de Pagamento, teremos uma pasta separada chamada `tests/security/`. Não vamos misturar testes funcionais (onde queremos apenas saber se o Pix foi gerado) com os testes de segurança. Todo endpoint de estorno (refund) ou criação de transação terá pelo menos um teste de BOLA e um teste de Mass Assignment garantindo que o lojista "A" não consiga estornar o Pix do lojista "B".

## 14. Perguntas de entrevista
- **Como você testaria uma API para garantir que um usuário não consiga ver a fatura de outro?**
  *Resposta*: Eu escreveria um teste simulando um ataque IDOR/BOLA. Faria autenticação como Usuário A, pegaria o ID de uma fatura dele, autenticaria como Usuário B e faria um GET passando o ID da fatura do Usuário A. O sistema deve retornar 403 ou 404.
- **O que é Mass Assignment em testes de API?**
  *Resposta*: É quando testamos se a API está vulnerável à injeção de propriedades não esperadas no payload. Por exemplo, passar `status: "PAGO"` em uma requisição de criação que deveria apenas iniciar o pedido como `PENDENTE`, para ver se o backend filtra corretamente.

## 15. Checklist
- [ ] Entendo a diferença entre BOLA (IDOR) e Broken Authentication.
- [ ] Sei como forjar um token localmente (mudando caracteres) para testar rejeição de assinaturas.
- [ ] Consigo escrever um script com Playwright usando dois tokens diferentes na mesma suíte de testes.
- [ ] Verifiquei se campos sensíveis como `saldo` não podem ser atualizados via Mass Assignment.

## 16. Critério para avançar
Você pode prosseguir para a próxima fase quando seu projeto Playwright possuir pelo menos 3 testes de segurança automatizados: um testando limite de taxa (Rate Limit/Brute force), um de BOLA (tentando acessar dados alheios) e um de Mass Assignment (injetando campos indevidos).
