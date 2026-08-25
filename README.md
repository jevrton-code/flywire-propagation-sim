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
interativa em navegador na v1. O MVP simula um único circuito tratável e
documentado; outros circuitos entram como opções adicionais em fases futuras
(ver Roadmap). O grafo completo não é carregado em nenhuma fase.

### Circuito do MVP: bússola / ring attractor do complexo central

153 neurônios (`EPG`, `EPGt`, `PEN_a`, `PEN_b`, `PEG`, `Delta7`), 2.695 conexões
reais extraídas do conectoma FlyWire (snapshot v783, limiar de 5 sinapses). É o
circuito recorrente mais bem caracterizado do cérebro da mosca: um "bump" de
atividade no *ellipsoid body* rastreia a direção da cabeça do animal. Detalhes
completos de proveniência, licença, regra excitatório/inibitório e limitações
assumidas em [`data/README.md`](data/README.md).

### Roadmap — próximos circuitos

O MVP entrega apenas o circuito acima. Já estão escopados e planejados para
fases seguintes:

- **Via olfativa** (ORNs → lobo antenal → corpo pedunculado) — circuito
  majoritariamente feed-forward, bom contraste com o ring attractor recorrente.
- **Detecção de *looming*/fuga** (LC4/LPLC2 → neurônio descendente gigante) —
  cadeia sensório-motora curta com saída comportamental clara.

A infraestrutura de dados já foi construída para suportar múltiplos circuitos
(`flywire_data.circuits` é um registro extensível) — ver §8 de
[`data/README.md`](data/README.md).

## Status

- [x] Fase 1 — Descoberta e escopo dos dados: subgrafo do ring attractor
  extraído e validado a partir de dados reais e públicos do FlyWire.
- [x] Fase 2 — Modelo de simulação: leaky integrate-and-fire discreto no
  tempo sobre o grafo real (`src/flywire_sim/`), rodável via CLI
  (`python -m flywire_sim.run`), com estímulo configurável e 89 testes de
  estabilidade numérica e propagação.
- [x] Fase 3 — Backend: API FastAPI (`src/flywire_api/`) com endpoints REST
  de metadados/grafo/proveniência e WebSocket de streaming da simulação
  passo a passo (`/ws/simulate`), rodável via `python -m flywire_api.run`
  (Swagger em `/docs`). 73 novos testes (233 no total).
- [ ] Fase 4 — Frontend (React)
- [ ] Fase 5 — Testes finais e revisão

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
