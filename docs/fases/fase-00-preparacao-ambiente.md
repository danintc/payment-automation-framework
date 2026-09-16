# Fase 0: Preparação do Ambiente

## 01. O que você vai aprender
Nesta fase, você aprenderá a configurar do zero todo o ambiente necessário para a criação de um framework moderno de automação de testes com Playwright e TypeScript. Sem atalhos, sem magia: você instalará e configurará cada peça fundamental.

## 02. Por que isso importa para um QA
Muitos QAs sabem escrever testes em um projeto que já existe, mas travam quando precisam criar a fundação do zero. Um SDET (Software Development Engineer in Test) deve ter total domínio sobre as ferramentas, controle de versão (Git) e ambiente de execução (Node e Docker). Isso elimina atritos ao debugar problemas em CI/CD no futuro.

## 03. Pré-requisitos
- Um computador com Windows, macOS ou Linux.
- Permissão de administrador para instalar softwares.
- Vontade de usar o terminal (linha de comando).

## 04. Conceitos
- **Node.js e npm**: O ecossistema de execução para TypeScript e Playwright.
- **Git e GitHub**: Ferramentas de versionamento de código e colaboração.
- **Docker**: Ferramenta para rodar bancos de dados (como PostgreSQL) em containers isolados, sem poluir sua máquina.
- **Playwright**: O motor de testes.
- **TypeScript**: A linguagem base que usaremos, que adiciona tipagem ao JavaScript.

## 05. Explicação mastigada
Para começar, você não deve usar um template pronto. Vamos fazer na mão.

1. **Instalações Globais (Instale no seu SO)**
   - Baixe e instale o **Node.js** (versão LTS).
   - Baixe e instale o **Git**.
   - Instale o **VS Code**.
   - Instale o **Docker Desktop** (ou Docker Engine).
   - Instale o **DBeaver** (cliente para visualizar o banco de dados).

2. **Verificando o ambiente**
   Abra seu terminal e digite:
   ```bash
   node --version
   npm --version
   git --version
   docker --version
   ```
   Se todos retornarem uma versão, você está pronto.

3. **Iniciando o Projeto**
   ```bash
   mkdir payment-automation-framework
   cd payment-automation-framework
   npm init -y
   ```

4. **Instalando Playwright e TypeScript**
   ```bash
   npm install -D @playwright/test typescript @types/node
   npx playwright install
   npx tsc --init
   ```

5. **Estrutura de Pastas**
   Crie a base do seu projeto:
   ```bash
   mkdir src tests
   ```

## 06. Exemplos
O arquivo `playwright.config.ts` é o coração do projeto. Crie ele na raiz com o mínimo necessário para rodar testes de API:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:3000',
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
  },
});
```

## 07. Código comentado
Neste momento não temos muito código, mas vamos entender o `package.json` gerado:

```json
{
  "name": "payment-automation-framework",
  "version": "1.0.0",
  "description": "Framework de testes de API",
  "scripts": {
    // Esse script vai permitir rodar os testes apenas digitando "npm test"
    "test": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.40.0",
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0"
  }
}
```

## 08. Exercício guiado (Nível 1 - Guided)
**Missão**: Crie o seu primeiro teste de saúde da API.
1. Crie o arquivo `tests/health.spec.ts`.
2. Escreva o seguinte código:
```typescript
import { test, expect } from '@playwright/test';

test('A API pública de pagamentos deve estar online', async ({ request }) => {
  const response = await request.get('https://pokeapi.co/api/v2/pokemon/ditto');
  expect(response.status()).toBe(200);
});
```
3. Rode `npm test` no terminal.

## 09. Exercício sozinho (Nível 2 - Semi-guided)
**Missão**: Versionar o seu código no Git.
1. Inicialize um repositório git na pasta `payment-automation-framework`.
2. Crie um arquivo `.gitignore` (não esqueça de ignorar `node_modules/` e `playwright-report/`).
3. Faça o commit inicial.

## 10. Desafio (Nível 3 - Challenge)
**Missão**: Conectar-se a um banco usando Docker.
1. Suba um banco PostgreSQL usando Docker (pesquise sobre `docker run postgres`).
2. Abra o DBeaver e conecte-se a esse banco rodando na porta 5432.
*Dica: Você precisará definir a variável de ambiente `POSTGRES_PASSWORD` no docker run.*

## 11. Erros comuns
- **Esquecer o `.gitignore`**: Commitar a pasta `node_modules` no GitHub (isso trava seu repositório).
- **Rodar comandos na pasta errada**: Sempre verifique se você está dentro da pasta do projeto antes de rodar `npm install`.
- **Docker sem permissão**: No Windows/Mac, o Docker Desktop precisa estar rodando no background.

## 12. Debugging
- Se o comando `npm` não for reconhecido, o Node.js não está no PATH do seu sistema. Reinstale marcando "Add to PATH".
- Se o Playwright falhar informando falta de browsers, execute `npx playwright install`.

## 13. Aplicação no projeto principal
Esta etapa cria o alicerce físico do projeto `payment-automation-framework`. Todos os outros módulos morarão aqui.

## 14. Perguntas de entrevista
- *O que acontece nos bastidores quando você digita `npm install`?*
- *Qual a diferença entre instalar uma dependência comum (`npm install pacote`) e uma dependência de desenvolvimento (`npm install -D pacote`)?*

## 15. Checklist
- [ ] Instalar ferramentas base (Node, Git, VSCode, Docker, DBeaver)
- [ ] Rodar comandos de versão e confirmar instalações
- [ ] Iniciar projeto npm
- [ ] Instalar Playwright e dependências TS
- [ ] Criar estrutura de pastas
- [ ] Rodar o primeiro teste de API
- [ ] Fazer commit no Git

## 16. Critério para avançar
Você só avança para a Fase 1 (TypeScript) se conseguir, sem ajuda:
- Criar um projeto;
- Instalar dependências;
- Versionar no Git (commit, push, criar branch, abrir PR);
- Subir um container Postgres no Docker.
