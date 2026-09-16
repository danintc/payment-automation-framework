import os

phases = [
    "00-preparacao-ambiente",
    "01-typescript-qa",
    "02-http-rest-apis",
    "03-playwright-api",
    "04-test-design",
    "05-arquitetura-framework",
    "06-api-testing-avancado",
    "07-postgresql-sql",
    "08-integracao-api-banco",
    "09-contract-testing",
    "10-ci-cd",
    "11-webhooks-assincrono",
    "12-concorrencia-idempotencia",
    "13-resiliencia-toxiproxy",
    "14-seguranca-apis",
    "15-observabilidade",
    "16-projeto-final-sdet"
]

titles = [
    "Fase 0: Preparação do Ambiente",
    "Fase 1: TypeScript para QA Automation",
    "Fase 2: HTTP + REST + APIs",
    "Fase 3: Playwright API - O Básico ao Avançado",
    "Fase 4: Test Design - Projetando antes de automatizar",
    "Fase 5: Arquitetura de Framework",
    "Fase 6: API Testing Avançado",
    "Fase 7: PostgreSQL + SQL - Trilha de Banco de Dados",
    "Fase 8: Integração API + Banco",
    "Fase 9: Contract Testing",
    "Fase 10: CI/CD - Pipelines e Automação",
    "Fase 11: Webhooks + Testes Assíncronos",
    "Fase 12: Concorrência + Idempotência",
    "Fase 13: Resiliência + Toxiproxy",
    "Fase 14: Segurança de APIs",
    "Fase 15: Observabilidade e Debugging",
    "Fase 16: Projeto Final SDET"
]

template = """# {title}

## 01. O que você vai aprender
*Detalhe aqui os objetivos de aprendizagem desta fase.*

## 02. Por que isso importa para um QA
*Contextualize a importância deste conhecimento no dia a dia de um SDET.*

## 03. Pré-requisitos
*O que o aluno precisa saber ou ter configurado antes de começar.*

## 04. Conceitos
*Teoria fundamental.*

## 05. Explicação mastigada
*Explicação detalhada, passo a passo, sem pular etapas.*

## 06. Exemplos
*Exemplos práticos do conceito.*

## 07. Código comentado
*Trechos de código com comentários linha a linha explicando o "porquê".*

## 08. Exercício guiado (Nível 1 - Guided)
*Instruções passo a passo para implementar uma solução.*

## 09. Exercício sozinho (Nível 2 - Semi-guided)
*Problema proposto para o aluno resolver com poucas dicas.*

## 10. Desafio (Nível 3 - Challenge)
*Cenário complexo (ex: bug em produção, falha de concorrência) para investigar e automatizar.*

## 11. Erros comuns
*Quais são as armadilhas mais frequentes ao aprender este tópico.*

## 12. Debugging
*Como investigar e resolver problemas relacionados a este tópico.*

## 13. Aplicação no projeto principal
*Como integrar o que foi aprendido no `payment-automation-framework`.*

## 14. Perguntas de entrevista
*O que um QA Pleno/SDET deveria conseguir explicar sobre isso numa entrevista?*

## 15. Checklist
- [ ] Tarefa 1
- [ ] Tarefa 2

## 16. Critério para avançar
*Você só avança para a próxima fase se conseguir:*
- *Critério 1*
- *Critério 2*
"""

base_dir = r"d:\cursos\playwright-api-study\docs\fases"
os.makedirs(base_dir, exist_ok=True)

for i, phase in enumerate(phases):
    filename = os.path.join(base_dir, f"fase-{phase}.md")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(template.format(title=titles[i]))

print("Arquivos Markdown gerados com sucesso!")
