# Simulador de Propagação de Sinal no Conectoma da Drosophila (FlyWire)

## Missão

Construir uma aplicação web que simula, de forma simplificada mas cientificamente
honesta, a propagação de ativação neural sobre um subconjunto real do conectoma
completo do cérebro da *Drosophila melanogaster* (dataset [FlyWire](https://codex.flywire.ai),
Nature 2024, ~140.000 neurônios / ~50 milhões de sinapses). O usuário escolhe um
neurônio (ou grupo de neurônios) de origem, injeta um "estímulo", e vê a ativação
se propagar pelo grafo real de conexões ao longo do tempo, com visualização
interativa.

Este **não** é um projeto de pesquisa em neurociência — é um projeto de portfólio
de engenharia que usa dados científicos reais e públicos de forma correta e
citável. Precisão de engenharia > sofisticação do modelo biológico.

## Stack

- **Dados**: FlyWire / CAVEclient (Python) — [codex.flywire.ai](https://codex.flywire.ai)
  e documentação do CAVE (Connectome Annotation and Versioning Engine).
- **Simulação**: Python (NetworkX para o grafo + modelo de disparo simplificado,
  ex: leaky integrate-and-fire ou um modelo linear de propagação por camadas).
- **Backend**: FastAPI + WebSocket para streaming dos passos da simulação.
- **Frontend**: React + biblioteca de grafo (ex: force-graph, D3, ou sigma.js).
- **Testes**: pytest (backend/simulação), vitest ou equivalente (frontend).

## Restrição de escopo (MVP)

O grafo completo (140k nós / 50M arestas) é grande demais para uma simulação
interativa em navegador na v1. Um subconjunto tratável do conectoma é escolhido
e justificado — por exemplo, um circuito documentado publicamente (sistema
olfativo, detecção de movimento visual) ou os N neurônios de maior grau de um
circuito. O grafo completo não é carregado na v1.

## Status

Projeto em fase inicial — ainda sem código de dados, simulação, backend ou
frontend. Este README será atualizado conforme cada fase for concluída.

## Critério de "pronto" para v1

- Simulação rodando ponta a ponta sobre dados reais do FlyWire (não dados
  sintéticos/fake).
- Frontend mostrando a propagação de forma visualmente clara.
- Testes automatizados passando para simulação e backend.
- Este README explicando o que é o FlyWire, de onde vêm os dados, o que o
  modelo de simulação simplifica/assume, e como rodar o projeto localmente.

## Citação dos dados

Os dados do conectoma vêm do projeto FlyWire:

> Dorkenwald, S., Matsliah, A., Sterling, A.R. et al. Neuronal wiring diagram
> of an adult brain. *Nature* 634, 124–138 (2024).
> https://doi.org/10.1038/s41586-024-07558-y

Acesso via [codex.flywire.ai](https://codex.flywire.ai) e CAVEclient.
