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

- **Dados**: extraídos do dump público de conectividade do FlyWire no Zenodo
  (sem necessidade de CAVEclient/token para o MVP — ver
  [`data/README.md`](data/README.md) §7).
- **Simulação**: Python + NetworkX, modelo *leaky integrate-and-fire* (LIF)
  discreto no tempo (`src/flywire_sim/`) — ver seção
  [Modelo de simulação](#modelo-de-simulação-o-que-ele-mostra-e-o-que-não-mostra)
  abaixo.
- **Backend**: FastAPI + WebSocket para streaming passo a passo
  (`src/flywire_api/`).
- **Frontend**: React + Vite, grafo desenhado com `react-force-graph-2d`
  (`frontend/`).
- **Testes**: pytest (dados/simulação/backend, 234 testes), vitest +
  Testing Library (frontend, 80 testes), e uma suíte de smoke test end-to-end
  com Playwright contra um backend e dev server reais
  (`frontend/scripts/browser-smoke.mjs`, 26 verificações).

## Restrição de escopo (MVP)

O grafo completo (140k nós / 50M arestas) é grande demais para uma simulação
interativa em navegador na v1. O MVP simula um único circuito tratável e
documentado; outros circuitos entram como opções adicionais em fases futuras
(ver Roadmap). O grafo completo não é carregado em nenhuma fase.

### Circuito do MVP: bússola / ring attractor do complexo central

153 neurônios (`EPG`, `EPGt`, `PEN_a`, `PEN_b`, `PEG`, `Delta7`), 2.695 conexões
reais extraídas do conectoma FlyWire (snapshot v783, limiar de 5 sinapses). É
um dos circuitos recorrentes mais bem caracterizados do cérebro da mosca —
Seelig & Jayaraman (2015), Turner-Evans et al. (2020) e Hulse et al. (2021)
descrevem como um "bump" de atividade no *ellipsoid body* rastreia a direção
da cabeça do animal. **A simulação deste projeto não reproduz esse bump** —
ver a seção seguinte. Detalhes completos de proveniência, licença, regra
excitatório/inibitório e limitações assumidas em
[`data/README.md`](data/README.md).

## Modelo de simulação — o que ele mostra e o que não mostra

A dinâmica é um **leaky integrate-and-fire (LIF) discreto no tempo**
(`src/flywire_sim/model.py`), escolhido por ser estruturalmente estável num
grafo 49% recorrente (uma propagação linear exigiria calibrar o raio espectral
da matriz de pesos bem no limite da instabilidade — ver o docstring do módulo
para a justificativa completa). Um passo é "uma rodada de transmissão
sináptica", não um milissegundo; `leak`, `threshold` e `refractory_steps` são
escolhas de engenharia para uma dinâmica estável e legível, não constantes
biológicas medidas.

**A conectividade é real; a dinâmica é uma caricatura.** Resumo honesto: dado
um estímulo em um ou mais neurônios, o modelo mostra como a ativação se
espalha pela conectividade medida — ele **não** prediz o que os neurônios reais
fazem, e **não** reproduz o *bump* localizado que é a função computacional real
do circuito (isso exigiria calibrar o balanço excitação/inibição com muito
mais cuidado do que um modelo simples e auditável deveria). A lista completa
de simplificações assumidas (limiar de 5 sinapses, Lei de Dale, ausência de
atrasos de condução, ausência de plasticidade sináptica, entre outras) é
gerada pelo próprio backend e exibida sem tradução ou resumo em qualquer
execução — via `GET /api/circuit` (campo `simplifications`) e no painel "O que
este simulador é — e o que não é" do frontend.

**Duas versões do sinal excitatório/inibitório coexistem, de propósito.** O
dataset versionado em `data/subgraphs/` usa a predição automática de
neurotransmissor do pipeline do artigo (`nt_source=predicted`: 113
excitatórios / 39 inibitórios / 1 modulatório), por fidelidade ao pipeline
original. A camada de simulação e a API, por padrão, usam a política
`known-first` (113 / 40 / 0): prioriza o neurotransmissor estabelecido na
literatura (Turner-Evans et al. 2020) sobre a predição automática, e só cai
para a predição nos 3 neurônios sem literatura estabelecida — isso inverte o
sinal de exatamente 2 neurônios de baixa confiança de predição (um `Delta7` e
um `PEN_b`), produzindo a arquitetura inibitória canônica do ring attractor.
Ambas as políticas são citáveis e ambas continuam disponíveis
(`?nt_policy=predicted|known-first` na API); a divergência exata é exposta em
`GET /api/circuit/provenance`. Ver `data/README.md` §6.3 para a análise
completa.

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
- [x] Fase 4 — Frontend: app React + Vite (`frontend/`) com visualização do
  grafo (3 layouts, incluindo um anel por tipo celular), streaming da
  animação via WebSocket, inspetor de neurônios, e um painel sempre visível
  com o disclaimer e as 13 simplificações do modelo. 80 testes automatizados
  (vitest) e uma suíte de smoke test end-to-end contra o backend real
  (`frontend/scripts/browser-smoke.mjs`, 26/26 checks).
- [x] Fase 5 — Revisão final (`qa-reviewer` + orquestrador): suítes completas
  re-executadas (233 + 80 + 26 checks), reconstrução bit-a-bit do subgrafo a
  partir dos dumps brutos originais, verificação de todos os DOIs citados via
  Crossref, correção de uma imprecisão factual na documentação do
  neurotransmissor (`data/README.md` §6.3), preenchimento das lacunas do
  README apontadas na revisão (seção de modelo de simulação, variáveis de
  ambiente), 3 pequenas correções de código (clamp de duração no frontend,
  default inconsistente na CLI, comentário enganoso em fixtures de teste), e
  1 novo teste de regressão (234 no total). V1 completa pelo critério abaixo.

## Rodando localmente

O subgrafo de dados (`data/subgraphs/*.csv`, ~370 KB) já vem commitado no
repositório — **não é preciso baixar os ~850 MB de dados brutos do FlyWire**
para rodar a simulação. Isso só é necessário se você quiser reconstruir o
subgrafo do zero (ver [`data/README.md`](data/README.md) §7).

```bash
# backend
python -m venv .venv && source .venv/bin/activate  # fish: source .venv/bin/activate.fish
pip install -e ".[dev]"
python -m flywire_api.run          # http://127.0.0.1:8000 (Swagger em /docs)
pytest                             # 234 testes

# frontend (outro terminal)
cd frontend && npm install
npm run dev                        # http://localhost:5173
npm run test -- --run              # 80 testes (vitest)
npm run typecheck                  # tsc -b
npm run smoke                      # smoke test end-to-end (exige os dois servidores no ar)
```

Variáveis de ambiente opcionais (nenhuma é necessária para rodar localmente
com os defaults):

| Variável | Efeito | Default |
| --- | --- | --- |
| `FLYWIRE_API_DATA_DIR` | Diretório onde a API procura `data/subgraphs/` | `data/` na raiz do repo |
| `FLYWIRE_API_MAX_CONCURRENT` | Simulações simultâneas antes de responder `503` | `4` |
| `FLYWIRE_API_CORS_ORIGINS` | Origens permitidas por CORS | `localhost:5173`/`:3000` |
| `FLYWIRE_CACHE_DIR` | Cache local dos dumps brutos, para reconstruir o subgrafo | `data/raw/` |
| `VITE_API_BASE` | URL absoluta da API para um build de produção do frontend | vazio (usa o proxy do Vite em dev) |
| `FLYWIRE_API_URL` | Alvo do proxy do Vite em desenvolvimento, se o backend não estiver em `127.0.0.1:8000` | `http://127.0.0.1:8000` |

## Critério de "pronto" para v1

- [x] Simulação rodando ponta a ponta sobre dados reais do FlyWire (não dados
  sintéticos/fake) — verificado por reconstrução bit-a-bit do subgrafo a
  partir dos dumps brutos originais na revisão da Fase 5.
- [x] Frontend mostrando a propagação de forma visualmente clara.
- [x] Testes automatizados passando para simulação e backend (234 testes
  Python + 80 testes de frontend).
- [x] Este README explicando o que é o FlyWire, de onde vêm os dados, o que o
  modelo de simulação simplifica/assume (ver "Modelo de simulação" acima), e
  como rodar o projeto localmente.

## Limitações conhecidas e próximos passos (v1.1)

- **Seletor de política de neurotransmissor na UI.** A API já suporta
  `predicted` e `known-first` (ver "Modelo de simulação" acima); o frontend
  hoje fixa `known-first`. Expor os dois lado a lado seria a demonstração
  mais direta de honestidade de dados que o projeto pode oferecer.
- **Mostrar os neurônios com sinal invertido na UI.** `GET
  /api/circuit/provenance` já retorna quais 2 neurônios têm o sinal alterado
  pela política `known-first`; exibi-los no painel do modelo tornaria essa
  escolha auditável visualmente, não só em texto.
- **Segundo circuito (via olfativa ou looming/fuga).** A infraestrutura já
  suporta múltiplos circuitos (`flywire_data.circuits`, `?circuit=` na API e
  no frontend) — falta só popular um segundo `Circuit` no registro.
- **Rodar o streaming do WebSocket fora do event loop principal**, por
  simetria com o caminho REST (hoje irrelevante na escala de 153 neurônios,
  mas relevante ao adicionar um circuito maior).
- A normalização de peso por grau de entrada (`in-degree`, default do modelo)
  descarta a diferença absoluta de sinapses de entrada entre neurônios — um
  neurônio com 11 sinapses de entrada fica tão fácil de excitar quanto um com
  697. É uma simplificação real e documentada no código
  (`SimulationGraph.normalised_weights`), mas ainda não está na lista de
  simplificações que chega ao usuário final.

## Citação dos dados

Os dados do conectoma vêm do projeto FlyWire, obtidos sem necessidade de
CAVEclient/token via o dump público de conectividade no Zenodo (ver
[`data/README.md`](data/README.md) para a proveniência completa, incluindo
licenciamento e todas as citações do circuito):

> Dorkenwald, S., Matsliah, A., Sterling, A.R. et al. Neuronal wiring diagram
> of an adult brain. *Nature* 634, 124–138 (2024).
> https://doi.org/10.1038/s41586-024-07558-y

Explorador oficial do dataset: [codex.flywire.ai](https://codex.flywire.ai).
