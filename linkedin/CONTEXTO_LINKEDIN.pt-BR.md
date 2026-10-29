# FlyWire Propagation Sim: documento de contexto para o LinkedIn

> **Idioma:** Português (Brasil) · English version: [`LINKEDIN_CONTEXT.en.md`](LINKEDIN_CONTEXT.en.md)
> **Última atualização:** 2026-10-29
> **Versão do projeto coberta:** v1 (commit `14d54c8`, 2026-08-25)
> **Repositório:** https://github.com/jevrton-code/flywire-propagation-sim

---

## 0. Para que serve este documento

Este arquivo é a **fonte única de contexto** para tudo o que for publicado sobre
este projeto no LinkedIn: posts, carrosséis (posts de documento em PDF),
vídeos de demonstração, comentários, atualizações de versão e a seção
"Projetos" do perfil. Ele pode ser usado por você ou entregue inteiro a um
assistente de IA.

Tudo aqui foi conferido contra o repositório (código, dados versionados,
`data/README.md`, testes e histórico do git) em 2026-10-29. Os 234 testes
Python e a simulação principal da §4 foram executados de novo nessa data.

**Como usar**

- **Para escrever um post:** leia §1 (resumos prontos), §5 (o que os
  resultados significam) e §6 (o que não afirmar), e escolha um ângulo em §12.
- **Para pedir a um assistente de IA:** entregue este arquivo e diga qual
  ângulo da §12 você quer, o idioma e o tamanho. Instrua-o a usar **apenas** os
  números da §4 e a respeitar a §6.
- **Quando o projeto mudar:** atualize primeiro a §4 (ficha técnica), a §8
  (linha do tempo) e a §20 (registro de alterações).

**Regras inegociáveis para qualquer texto público**

1. A frase que resume o projeto é **"conectividade real, dinâmica
   simplificada"**. Nunca chame a simulação de "biologicamente realista".
2. Nunca diga que o modelo reproduz o *bump* do ring attractor nem que prevê o
   comportamento da mosca. Ele não faz isso, e o README diz isso.
3. É um projeto de **portfólio de engenharia** com dados científicos reais,
   não uma pesquisa em neurociência.
4. Creditar o FlyWire e os artigos (§15). Os dados derivados carregam a
   cláusula **não comercial** (CC-BY-NC 4.0).
5. O repositório ainda **não tem arquivo de licença para o código** (§18).
   Não diga "open source" até isso ser resolvido; diga "público no GitHub".

---

## 1. Resumos prontos (do mais curto ao mais longo)

**Uma linha (bio, legenda de vídeo, título de carrossel)**

> Simulador web de propagação neural sobre um circuito real do conectoma da
> mosca-da-fruta (FlyWire): conectividade real, dinâmica simplificada.

**Gancho (cabe antes do "ver mais")**

> Peguei um circuito real do cérebro de uma mosca, mapeado sinapse a sinapse,
> e construí um app para ver a atividade se espalhar por ele. E escrevi na
> tela tudo o que o modelo não faz.

**Gancho alternativo (resultado)**

> Estimulei 24 neurônios de um circuito real de 153. Em dois passos a
> atividade chegou aos seis tipos celulares; em cerca de 30, o circuito
> silenciou.

**Resumo curto (para post rápido ou comentário)**

> Construí uma aplicação web que simula a propagação de atividade neural sobre
> um circuito real do conectoma da Drosophila (FlyWire, Nature 2024): o
> circuito de bússola do complexo central, com 153 neurônios e 2.695 conexões
> reais. Back-end em FastAPI com streaming por WebSocket, front-end em React e
> um modelo leaky integrate-and-fire simples e auditável. A conectividade é
> real; a dinâmica é uma caricatura, e o app diz isso na tela.

**Descrição para a seção "Projetos" do perfil (cerca de 1.690 caracteres;
limite do LinkedIn: 2.000)**

```text
Aplicação web que simula a propagação de atividade neural sobre um circuito real do conectoma da Drosophila (FlyWire, Nature 2024), com visualização interativa passo a passo.

O que fiz
• Extraí do dump público do FlyWire (snapshot v783, cerca de 852 MB) o circuito de bússola do complexo central: 153 neurônios e 2.695 conexões reais, com verificação de MD5 e reconstrução bit a bit conferida na revisão final.
• Atribuí o sinal excitatório/inibitório pelo neurotransmissor, seguindo a regra do artigo original, e deixei auditáveis as divergências entre predição automática e literatura (148 de 150 neurônios concordam).
• Implementei um modelo leaky integrate-and-fire discreto, estável por construção num grafo em que 49% das conexões são recíprocas.
• Criei uma API em FastAPI com endpoints REST e streaming da simulação passo a passo via WebSocket.
• Construí um front-end em React + Vite com três layouts de grafo, inspetor de neurônios e um painel sempre visível com as 13 simplificações do modelo.
• Escrevi 234 testes Python, 80 testes de front-end e um smoke test end-to-end com Playwright.

Resultado
Estimular os 24 neurônios EPG do hemisfério esquerdo recruta 146 dos 153 neurônios, dos seis tipos celulares; a atividade reverbera e o circuito silencia por volta do passo 32.

Escopo honesto: conectividade real, dinâmica simplificada. O modelo mostra como a ativação se espalha pela fiação medida, mas não prevê o que os neurônios reais fazem nem reproduz o "bump" do ring attractor. É um projeto de portfólio de engenharia, não uma pesquisa em neurociência.

Stack: Python, NetworkX, NumPy, pandas, FastAPI, WebSocket, React, TypeScript, Vite, pytest, vitest, Playwright.
```

**Campos sugeridos da seção "Projetos"**

| Campo | Sugestão |
| --- | --- |
| Nome do projeto | FlyWire Propagation Sim: propagação neural sobre o conectoma real da Drosophila |
| Data | ago. de 2026 (v1 concluída em 2026-08-25) |
| Competências | Python · FastAPI · React · TypeScript · Neurociência computacional |
| Mídia | Link do repositório + captura de tela ou vídeo do app (ainda não existe; ver §10) |
| Associado a | [A PREENCHER: experiência, curso ou "projeto pessoal"] |

---

## 2. O problema e a motivação

### Em linguagem simples

Um **conectoma** é o mapa completo de quais neurônios se conectam com quais.
Em 2024, o consórcio **FlyWire** publicou na *Nature* o conectoma do cérebro
inteiro de uma mosca-da-fruta adulta: cerca de 140 mil neurônios e 50 milhões
de sinapses, reconstruídos a partir de imagens de microscopia eletrônica.

Este projeto pega um pedaço real desse mapa (o circuito que funciona como uma
**bússola** no cérebro da mosca, rastreando a direção da cabeça) e deixa o
usuário injetar um "estímulo" em neurônios escolhidos para ver a ativação se
espalhar pelas conexões reais, passo a passo, num navegador.

### Por que este circuito

- É o circuito recorrente mais bem caracterizado do cérebro dos insetos e o
  exemplo clássico de *ring attractor* biológico.
- É **fortemente recorrente** (49% das conexões fazem parte de um par
  recíproco), então a propagação tem estrutura e não é uma simples cascata.
- **Mistura excitação e inibição** de forma essencial.
- Seu comportamento esperado está publicado, então qualquer pessoa pode
  comparar a simulação com a biologia conhecida.
- Tem o tamanho certo: 153 neurônios cabem numa visualização interativa; o
  conectoma inteiro não caberia.

### A proposta do projeto

"Precisão de engenharia > sofisticação do modelo biológico" (README). O valor
está em usar dados científicos reais **de forma correta e citável**: cada
número rastreável até a fonte, cada simplificação declarada.

### Motivação pessoal do autor

[A PREENCHER: por que conectômica, o que te atraiu no FlyWire, o que queria
aprender. Ver §19.]

---

## 3. O que foi construído

### Arquitetura

```text
Fontes públicas (sem token, sem CAVEclient)
  ├─ Zenodo 10.5281/zenodo.10676866 — proofread_connections_783.feather (~852 MB, MD5 conferido)
  └─ GitHub flyconnectome/flywire_annotations v2.1.0 — tipos celulares e neurotransmissores
        │
        ▼
flywire_data  (extração e validação)
  • filtra os 6 tipos do circuito; limiar ≥ 5 sinapses; soma sobre neurópilos
  • sinal E/I pelo neurotransmissor pré-sináptico (lei de Dale)
  • falha em vez de inventar valores; registra a proveniência
        │
        ▼
data/subgraphs/  (versionado no git, ~250 KB em CSV + JSON)
  153 neurônios · 2.695 conexões · metadados de proveniência e citações
        │
        ▼
flywire_sim  (modelo)
  • leaky integrate-and-fire discreto, adimensional, com pesos normalizados por grau de entrada
  • CLI: python -m flywire_sim.run
        │
        ▼
flywire_api  (FastAPI)
  • REST: /api/health, /api/circuit, /neurons, /edges, /graph, /cell-types, /provenance, /api/model/defaults
  • POST /api/simulations (execução completa)
  • WS /ws/simulate (um quadro por passo, conforme é calculado)
        │
        ▼
frontend  (React + Vite + TypeScript, react-force-graph-2d)
  • 3 layouts: anel por tipo celular · posição do soma · força (conectividade)
  • painel de estímulo, controles de reprodução, linha do tempo de atividade
  • inspetor de neurônios, relatório da execução
  • painel sempre visível "O que este simulador é — e o que não é"
```

### O modelo, em uma frase

Cada neurônio guarda uma variável de membrana; a cada passo ela vaza uma
fração, soma a entrada sináptica de quem disparou no passo anterior e, se
passar de um limiar, o neurônio dispara, volta ao repouso e fica brevemente
refratário.

### Por que LIF e não um modelo linear

Num grafo recorrente, um modelo linear (`a[t+1] = leak·a[t] + W·a[t]`) depende
inteiramente do raio espectral de `W`: um pouco acima, a atividade explode; um
pouco abaixo, morre. Seria preciso calibrar o modelo bem no limite da
instabilidade, e qualquer mudança nos dados o tiraria de lá. No LIF, cada
neurônio só transmite um disparo binário, então a entrada de cada passo tem um
teto estrutural; com a normalização por grau de entrada, esse teto é
exatamente o `gain`. O estado não tem como divergir.

### A interface (o que aparece na tela)

- **Três layouts**, cada um com uma explicação honesta do que significa:
  - *Anel por tipo celular* (padrão): layout de apresentação, agrupado por
    hemisfério e tipo; **não** é a geometria anatômica.
  - *Posição do soma*: projeção XY das coordenadas reais do corpo celular.
  - *Força (conectividade)*: revela agrupamentos; posições sem significado
    anatômico.
- **Painel de estímulo**: escolher neurônios por tipo, hemisfério ou ID.
- **Streaming via WebSocket** com controles de reprodução.
- **Inspetor de neurônios** e **linha do tempo de atividade**.
- **Filtro de exibição** de conexões fracas (padrão: ≥ 15 sinapses), que
  **não altera a simulação**, só o desenho.
- **Painel de honestidade** sempre visível, com o aviso e as 13 simplificações
  vindas diretamente da API.
- A interface está em **português**.

### Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m flywire_api.run          # http://127.0.0.1:8000 (Swagger em /docs)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## 4. Ficha técnica (números verificados)

### Fontes de dados

| Item | Valor | Fonte |
| --- | --- | --- |
| Conectoma completo | ~140 mil neurônios, ~50 milhões de sinapses (Dorkenwald et al., *Nature* 2024) | `README.md` |
| Dump de conectividade | `proofread_connections_783.feather`, 852.022.274 bytes, snapshot v783 | `data/README.md` §2.1 |
| Linhas do dump antes do filtro | 16.847.997 | `data/README.md` §2.1 |
| DOI do dump | 10.5281/zenodo.10676866 | `data/README.md` |
| Anotações | `flywire_annotations` v2.1.0 (2024-07-30), 139.255 neurônios | `data/README.md` §2.2 |
| Integridade | MD5 conferido contra o checksum publicado a cada execução | `data/README.md` |
| Credenciais necessárias | Nenhuma (acesso HTTP anônimo) | `data/README.md` §7 |
| Licença do dump | CC-BY-4.0 | `data/README.md` §2.3 |
| Licença das anotações | CC-BY-NC 4.0 (Termos do FlyWire); governa o produto derivado | `data/README.md` §2.3 |

### O subgrafo (anotações v2.1.0 + conectividade v783, limiar ≥ 5 sinapses)

| Métrica | Valor |
| --- | --- |
| Neurônios | **153** |
| Conexões dirigidas | **2.695** |
| Sinapses totais | 38.141 |
| Pares recíprocos | 1.328 (49% das conexões) |
| Nós órfãos / auto-laços | 0 / 0 |
| Sinapses por conexão (mín. / mediana / máx.) | 5 / 10 / 89 |
| Hemisférios | 77 direita, 76 esquerda |
| Neurópilos principais | PB, EB, NO, GA_L/GA_R |
| Tamanho dos arquivos versionados | cerca de 250 KB (3 arquivos em `data/subgraphs/`) |

### Composição por tipo celular

| Tipo | N | Neurotransmissor | Sinal |
| --- | ---: | --- | --- |
| EPG | 47 | acetilcolina | excitatório |
| EPGt | 4 | acetilcolina | excitatório |
| PEG | 20 | acetilcolina | excitatório |
| PEN_a (PEN1) | 20 | acetilcolina | excitatório |
| PEN_b (PEN2) | 22 | acetilcolina | excitatório (1 exceção na predição) |
| Delta7 | 40 | glutamato | inibitório (1 exceção na predição) |

### Excitação e inibição

| Política de neurotransmissor | Neurônios E / I / modulatório | Uso |
| --- | --- | --- |
| `predicted` (predição automática do artigo) | 113 / 39 / 1 | Dataset versionado |
| `known-first` (literatura primeiro) | 113 / 40 / 0 | Padrão da simulação e da API |

- Conexões na política `predicted`: 2.088 excitatórias, 585 inibitórias, 22
  modulatórias (peso 0, todas de um único neurônio).
- **Concordância entre predição e literatura: 148 de 150 neurônios (98,7%).**
  As 2 divergências estão entre as três predições de menor confiança do
  conjunto (0,354 e 0,402).
- Acurácia relatada do classificador de neurotransmissores (Eckstein et al.,
  2024): 87% por sinapse e 94% por neurônio.

### Versão das anotações

| Anotações | Neurônios | Conexões |
| --- | ---: | ---: |
| v2.1.0 (padrão, a citada nos artigos de 2024) | 153 | 2.695 |
| v3.1.0 | 155 | 2.716 |

A diferença são 2 neurônios Delta7. A v2.1.0 foi escolhida por
citabilidade.

### Parâmetros padrão do modelo (escolhas de engenharia, não constantes biológicas)

| Parâmetro | Valor |
| --- | --- |
| `threshold` | 0,20 |
| `leak` | 0,9 por passo |
| `refractory_steps` | 3 |
| `gain` | 1,0 |
| Normalização dos pesos | por grau de entrada (`in-degree`) |
| `noise_std` | 0 (sem ruído) |
| Passos máximos por simulação (API) | 500 |
| Simulações simultâneas antes de responder `503` | 4 |

### Resultado principal (reexecutado em 2026-10-29)

Comando: `python -m flywire_sim.run --source-type EPG --source-side left`
(parâmetros padrão, 50 passos).

| Métrica | Valor |
| --- | --- |
| Neurônios estimulados | 24 (todos os EPG do hemisfério esquerdo) |
| Neurônios que dispararam | **146 de 153 (95,4%)** |
| Neurônios a jusante recrutados | 122 |
| Tipos celulares atingidos | os 6 |
| Primeiro disparo dos tipos a jusante | passo 2 |
| Pico | passo 6, com 61 neurônios disparando |
| Último disparo | passo 31; silêncio total a partir do passo 32 |
| Total de disparos | 785 |
| Estado numérico | finito; membrana máxima \|V\| = 1,0 |

Por tipo: EPG 47/47, EPGt 3/4, PEG 19/20, PEN_a 20/20, PEN_b 22/22,
Delta7 35/40.

### Outros comportamentos documentados (docstring de `model.py`)

- **Estimular um único EPG é bem mais fraco:** com a normalização por grau de
  entrada, um parceiro pré-sináptico carrega em mediana 4% da entrada do alvo.
  41 dos 47 EPG recrutam pelo menos um parceiro direto (mediana de 2); 6 não
  recrutam nenhum.
- **Regime saturado:** com `refractory_steps` em 0 ou 1, ou `threshold`
  abaixo de cerca de 0,15, o circuito entra num regime autossustentado. É o
  esperado para uma rede recorrente, isolada e dominada por excitação (113
  excitatórios × 40 inibitórios).

### Qualidade e tamanho

- **Testes Python: 234 passando** (dados, simulação e API; reexecutado em
  2026-10-29, cerca de 4 s).
- **Testes de front-end: 80** (vitest + Testing Library), segundo o README.
- **Smoke test end-to-end: 26 verificações** com Playwright contra back-end e
  dev server reais, segundo o README.
- Revisão final: reconstrução bit a bit do subgrafo a partir dos dumps
  originais e verificação de todos os DOIs citados via Crossref.
- 3 pacotes Python (`flywire_data`, `flywire_sim`, `flywire_api`) e um
  front-end React com 8 componentes de interface.

---

## 5. Resultados e interpretação (as histórias que os números contam)

### 5.1 Conectividade real, dinâmica simplificada

A frase do próprio código ("*real wiring, toy dynamics*") é o coração da
comunicação. O valor do projeto não está em "simular o cérebro de uma mosca",
e sim em **usar um dado científico de ponta com rigor de engenharia** e ser
explícito sobre o que o modelo não faz.

### 5.2 Uma cascata que chega a todo o circuito e depois se apaga

Estimular os 24 EPG esquerdos recruta 95% do circuito em poucos passos, com
pico no passo 6, e o circuito silencia no passo 32. É a demonstração visual
mais forte do app.

### 5.3 Um neurônio sozinho quase não faz nada (e isso não é bug)

Com a normalização por grau de entrada, uma única conexão representa em
mediana 4% da entrada do alvo. A diferença entre estimular 1 e 24 neurônios é
uma boa história sobre como **escolhas de normalização mudam o
comportamento** de um modelo.

### 5.4 O modelo não reproduz o *bump*, e diz isso

A função real deste circuito é manter um único "bump" de atividade que
rastreia a direção da cabeça. Reproduzir isso exigiria calibrar o equilíbrio
entre excitação e inibição com muito mais cuidado do que um modelo simples e
auditável deveria. O app diz isso na tela.

### 5.5 Quando a predição automática discorda da literatura

A predição automática de neurotransmissores concorda com a literatura em
148 de 150 neurônios. As 2 discordâncias estão justamente entre as predições
de menor confiança. Em vez de "corrigir à mão" ou esconder, o projeto mantém
**as duas políticas** disponíveis e expõe exatamente onde elas divergem
(`GET /api/circuit/provenance`).

---

## 6. O que pode e o que não pode ser dito

| ✅ Pode dizer | ❌ Não diga | Por quê |
| --- | --- | --- |
| "Simula a propagação de ativação sobre conexões reais do FlyWire" | "Simula o cérebro da mosca" / "biologicamente realista" | É um subcircuito de 153 neurônios com dinâmica simplificada. |
| "Conectividade real, dinâmica simplificada" | "Prevê o que os neurônios fazem" | O modelo não é calibrado com dados de atividade. |
| "Mostra como a ativação se espalha pela fiação medida" | "Reproduz o ring attractor" / "reproduz o bump" | O README diz explicitamente que não reproduz. |
| "Um passo = uma rodada de transmissão sináptica" | "Em X milissegundos..." | O tempo é adimensional. |
| "Projeto de portfólio de engenharia com dados científicos reais" | "Pesquisa em neurociência" / "descoberta" | O próprio README se define assim. |
| "Público no GitHub" | "Open source" | Ainda não há arquivo de licença para o código. |
| "Dados do FlyWire (Dorkenwald et al., 2024), uso não comercial" | Qualquer sugestão de uso comercial dos dados | As anotações são CC-BY-NC 4.0. |
| "234 testes Python, 80 de front-end, smoke test end-to-end" | "100% de cobertura" | Cobertura não foi medida. |
| "Extraí um subgrafo do conectoma" | "Mapeei o conectoma" | O mapeamento é do consórcio FlyWire. |

---

## 7. Decisões de engenharia (bastidores que viram conteúdo)

1. **Falhar em vez de inventar.** Se uma fonte não puder ser obtida ou um
   neurotransmissor não for reconhecido, o pipeline lança erro. Não existe
   sinal padrão silencioso.
2. **Integridade verificável.** MD5 do dump conferido a cada execução contra o
   checksum do Zenodo; reconstrução bit a bit do subgrafo na revisão final.
3. **CSV em vez de parquet para o subgrafo.** Os arquivos são pequenos, então
   CSV deixa o dado legível e "diffável" no git, o que permite auditar mudanças.
4. **Sem credenciais.** O MVP usa só fontes públicas e anônimas, sem
   CAVEclient nem token.
5. **Citabilidade acima de 2 neurônios a mais.** Escolha da anotação v2.1.0
   (153 neurônios) em vez da v3.1.0 (155), porque é a versão citada nos
   artigos da *Nature* de 2024. A v3.1.0 continua disponível por parâmetro.
6. **Modulatórios com peso 0, explicitamente.** Serotonina, dopamina e
   octopamina não têm sinal determinado pelo transmissor; em vez de chutar,
   recebem peso 0 e ficam marcados como `modulatory`.
7. **Duas políticas de neurotransmissor, lado a lado.** `predicted` (fiel ao
   pipeline do artigo) e `known-first` (prioriza a literatura). A divergência
   exata é exposta pela API.
8. **LIF em vez de modelo linear.** Estável por construção num grafo
   recorrente, sem calibração no limite da instabilidade (§3).
9. **Parâmetros como escolhas de engenharia.** `leak`, `threshold` e
   `refractory_steps` foram escolhidos por varredura, para uma dinâmica estável
   e legível, e são apresentados assim; nada foi ajustado a dados biológicos.
10. **A honestidade viaja com o dado.** As 13 simplificações são uma constante
    no código (`SIMPLIFICATIONS`), enviada pela API e mostrada no front-end, em
    vez de ficar escondida numa docstring.
11. **`root_id` sempre como string.** Os IDs do FlyWire têm 18 dígitos e
    estouram o maior inteiro seguro do `Number` do JavaScript.
12. **Valores por neurônio em arrays alinhados à ordem enviada no cabeçalho do
    stream**, para mensagens WebSocket compactas.
13. **Layouts que dizem o que são.** O anel é rotulado como layout de
    apresentação, não como anatomia.
14. **Filtro visual separado da simulação.** Esconder conexões fracas muda o
    desenho, nunca o cálculo.
15. **Limite de concorrência.** Até 4 simulações simultâneas; acima disso, a
    API responde `503` em vez de degradar.
16. **Arquitetura extensível.** `flywire_data.circuits` é um registro de
    circuitos; adicionar a via olfativa ou o circuito de fuga é adicionar uma
    entrada.

---

## 8. Linha do tempo

| Data (2026-08-25) | Fase | Commit | O que entrou |
| --- | --- | --- | --- |
| 13:24 | — | `5c17a70` | Commit inicial: `.gitignore` e README do projeto |
| 14:03 | Fase 1 | `e7a69d9` | Extração do subgrafo do ring attractor a partir do FlyWire real |
| 17:27 | Fase 2 | `0be8753` | Modelo LIF discreto sobre o grafo |
| 17:47 | Fase 3 | `1f2958c` | API FastAPI com REST e streaming via WebSocket |
| 23:37 | Fase 4 | `73725bf` | Front-end React + Vite |
| 23:57 | Fase 5 | `14d54c8` | Revisão final: lacunas da v1 fechadas |

Não há tag nem *release* criada no GitHub (ver §18).

---

## 9. Stack e competências

**Back-end e dados:** Python 3.11+, pandas, pyarrow, NumPy, NetworkX, FastAPI,
Pydantic v2, Uvicorn, WebSocket, pytest, httpx.

**Front-end:** React 19, TypeScript, Vite, react-force-graph-2d, vitest,
Testing Library, Playwright.

**Competências para marcar no LinkedIn**

- Python
- FastAPI
- React.js
- TypeScript
- WebSockets
- Neurociência computacional (Computational Neuroscience)
- Ciência de redes / Teoria dos grafos
- Engenharia de dados
- Desenvolvimento full-stack
- Testes de software

**Competências demonstradas, em linguagem de recrutador**

- Levar um dado científico complexo de ponta a ponta: extração, validação,
  modelo, API e interface.
- Projetar APIs com contrato claro (REST + streaming).
- Testar em várias camadas (unidade, API, front-end, end-to-end).
- Tratar proveniência, licenças e limitações como requisitos de produto.

---

## 10. Ativos visuais

**Não há nenhuma imagem do app versionada no repositório.** Este é o maior
ponto a resolver antes de divulgar o projeto: é o mais visual dos três, e hoje
um post não teria o que mostrar.

**Lista de capturas sugerida**

| # | O quê | Formato sugerido | Uso |
| --- | --- | --- | --- |
| 1 | Layout em anel no pico da propagação (passo 6 do estímulo nos EPG esquerdos) | Imagem 1080×1350 ou 1200×1200 | Imagem principal |
| 2 | Vídeo curto (15–30 s) da propagação, do estímulo ao silêncio | Vídeo nativo, vertical ou quadrado | Post de lançamento |
| 3 | Mesmo estímulo nos três layouts (anel, soma, força) | Carrossel | Post sobre "layouts honestos" |
| 4 | Painel "O que este simulador é — e o que não é" | Imagem | Post sobre honestidade de dados |
| 5 | Inspetor de neurônio mostrando um `root_id` e suas conexões | Imagem | Post técnico |
| 6 | Swagger da API (`/docs`) | Imagem | Post para back-end |
| 7 | Linha do tempo de atividade (disparos por passo) | Imagem | Post sobre o resultado (§4) |

**Roteiro sugerido de carrossel (8 slides, 1080×1350)**

1. Capa: "153 neurônios reais de uma mosca, no navegador".
2. O que é um conectoma e o FlyWire (Nature 2024).
3. O circuito de bússola: tipos celulares e por que ele foi escolhido.
4. Do dump de 852 MB ao subgrafo de cerca de 250 KB (pipeline com MD5).
5. O modelo em uma frase + por que LIF e não linear.
6. A cascata: 24 estimulados → 146 recrutados → silêncio no passo 32.
7. O que o simulador NÃO é (as simplificações).
8. Stack, testes, link do GitHub e créditos.

**Também falta:** imagem de *social preview* do GitHub (1280×640) e,
idealmente, uma demo on-line (por exemplo, front-end estático + API
hospedada), já que a maioria das pessoas não vai rodar o projeto localmente.

---

## 11. Público, posicionamento e tom

### Para quem os posts falam

| Público | O que procura | O que destacar |
| --- | --- | --- |
| Recrutadores e gestores técnicos | Capacidade de entregar produto completo | Full-stack, testes em várias camadas, entregas por fases |
| Engenharia de software (back e front) | Decisões de arquitetura | WebSocket, contrato da API, `root_id` como string, limite de concorrência |
| Dados e ciência | Proveniência e integridade | MD5, reconstrução bit a bit, duas políticas de neurotransmissor |
| Neurociência computacional e conectômica | Rigor e domínio | FlyWire, ring attractor, regra E/I, simplificações declaradas |
| Público geral curioso | Ver o "cérebro de uma mosca" funcionando | Vídeo da propagação, explicação simples |

### Posicionamento sugerido

> Engenharia de software com dados científicos reais: do dump bruto à
> interface, com proveniência verificável e limites declarados na própria
> tela.

### Tom de voz

- Primeira pessoa, entusiasmado com o dado, rigoroso com as afirmações.
- A frase "conectividade real, dinâmica simplificada" deve aparecer em todo
  post de visão geral.
- Evitar "simulei o cérebro", "IA que pensa como mosca" e similares.
- Parágrafos curtos; poucos emojis, se algum.

### Notas de formato do LinkedIn (confira, os limites mudam)

- Post: até 3.000 caracteres; o gancho precisa caber nas primeiras linhas
  (cerca de 200 caracteres) antes do "ver mais".
- Descrição na seção "Projetos": até 2.000 caracteres.
- Vídeo nativo é o formato natural para este projeto; mantenha curto e com
  legenda, já que muita gente assiste sem som.
- Carrossel: post de documento em PDF com slides verticais (1080×1350).
- Hashtags: 3 a 5 relevantes.

---

## 12. Banco de ângulos para posts

### A. Lançamento
- **Gancho:** "Peguei um circuito real do cérebro de uma mosca, mapeado sinapse
  a sinapse, e construí um app para ver a atividade se espalhar por ele."
- **Pontos:** FlyWire; 153 neurônios e 2.695 conexões reais; stack; o
  resultado da cascata; "conectividade real, dinâmica simplificada".
- **Visual:** vídeo da propagação (captura 2 da §10).
- **CTA:** link do GitHub; "que circuito você gostaria de ver depois?"

### B. A tela que diz o que o modelo não faz
- **Gancho:** "A parte do meu app de que mais me orgulho é um painel que lista
  13 coisas que ele não faz."
- **Pontos:** `SIMPLIFICATIONS` no código → API → front-end; honestidade que
  viaja com o dado.
- **Visual:** captura 4.

### C. Por que não um modelo linear
- **Gancho:** "O modelo mais simples era instável. O um pouco mais complexo era
  estável por construção."
- **Pontos:** raio espectral; 49% de recorrência; teto estrutural do LIF.
- **Público:** engenharia, ML, neurociência computacional.

### D. 18 dígitos que quebram o JavaScript
- **Gancho:** "Um ID de neurônio quebrou meu front-end. A solução foi tratá-lo
  como texto."
- **Pontos:** IDs de 18 dígitos × inteiro seguro do `Number`; contrato da API;
  arrays alinhados.
- **Público:** desenvolvedores (post curto e técnico).

### E. Do dump de 852 MB ao CSV de 250 KB
- **Gancho:** "Baixar 852 MB para ficar com cerca de 250 KB, e conseguir
  provar que cada byte está certo."
- **Pontos:** MD5; falhar em vez de inventar; reconstrução bit a bit; CSV
  diffável.
- **Público:** dados.

### F. Quando a IA discorda da literatura
- **Gancho:** "A predição automática concordou com a literatura em 148 de 150
  neurônios. O que eu fiz com os outros 2?"
- **Pontos:** confiança das predições; duas políticas lado a lado; nada
  corrigido à mão em silêncio.
- **Público:** ciência de dados, IA.

### G. 2 neurônios a menos, uma citação mais forte
- **Gancho:** "Escolhi a versão do dataset com menos neurônios. De propósito."
- **Pontos:** v2.1.0 × v3.1.0; citabilidade; a outra versão continua
  disponível.

### H. Licenças importam
- **Gancho:** "Os dados são abertos. Isso não significa que eu possa fazer
  qualquer coisa com eles."
- **Pontos:** CC-BY-4.0 × CC-BY-NC 4.0; a cláusula mais restritiva governa.

### I. Um neurônio sozinho
- **Gancho:** "Estimulei um neurônio e quase nada aconteceu. Estimulei 24 e o
  circuito inteiro respondeu."
- **Pontos:** normalização por grau de entrada; 4% de mediana; o que isso diz
  sobre escolhas de modelagem.

### J. Testando em todas as camadas
- **Gancho:** "234 + 80 + 26: como testei um app de neurociência de ponta a
  ponta."
- **Pontos:** testes de dados, modelo, API, componentes e smoke test com
  Playwright contra servidores reais.
- **Público:** engenharia.

### K. (Opcional) Como o projeto foi construído
- Use só se fizer sentido para você (§19). O README cita uma revisão final por
  `qa-reviewer` + orquestrador. Se o desenvolvimento usou agentes de IA, um
  post sobre "como organizei o trabalho em fases com revisão rigorosa" pode
  ser um ângulo forte e transparente.

### L. Série com os outros projetos
- **Gancho:** "Do sinal no couro cabeludo ao mapa de fiação do cérebro."
- **Pontos:** ligação com os projetos de EEG e BCI (§17).

---

## 13. Glossário para linguagem acessível

| Termo | Explicação simples |
| --- | --- |
| **Conectoma** | Mapa completo de quais neurônios se conectam com quais. |
| **FlyWire** | Consórcio que reconstruiu o conectoma do cérebro inteiro de uma mosca adulta (publicado na *Nature* em 2024). |
| ***Drosophila melanogaster*** | A mosca-da-fruta, um dos organismos mais estudados da biologia. |
| **Sinapse** | Ponto de contato onde um neurônio passa sinal para outro. |
| **Neurotransmissor** | Molécula usada na sinapse; ajuda a determinar se o efeito é excitatório ou inibitório. |
| **Excitatório / inibitório** | Conexão que aumenta / diminui a chance de o neurônio seguinte disparar. |
| **Lei de Dale** | Simplificação de que cada neurônio libera um único transmissor em todas as suas saídas. |
| **Ring attractor** | Circuito em anel que mantém um único "bump" de atividade; na mosca, funciona como bússola. |
| **Bump** | Grupo localizado de neurônios ativos cuja posição no anel representa a direção. |
| **EPG, PEN, PEG, Delta7** | Tipos de neurônio do circuito de bússola (carregam, deslocam, realimentam e inibem o bump). |
| **LIF (leaky integrate-and-fire)** | Modelo simples de neurônio: acumula entrada, "vaza" com o tempo e dispara ao passar de um limiar. |
| **Raio espectral** | Número que diz se a atividade num modelo linear cresce ou some com o tempo. |
| **WebSocket** | Conexão aberta entre navegador e servidor para enviar dados em tempo real. |
| **Snapshot v783** | Versão congelada do conectoma usada nos artigos de 2024. |

---

## 14. Hashtags e palavras-chave

**Hashtags (escolha de 3 a 5 por post)**

- Núcleo: `#Connectomics` `#ComputationalNeuroscience` `#Python` `#FastAPI`
  `#React`
- Alcance em português: `#Neurociência` `#NeurociênciaComputacional`
  `#DesenvolvimentoWeb` `#CiênciaDeDados`
- Alcance em inglês: `#Neuroscience` `#OpenScience` `#DataVisualization`
  `#FullStack` `#WebSockets`

**Palavras-chave para busca e SEO do perfil:** conectoma, FlyWire,
Drosophila, neurociência computacional, ring attractor, leaky
integrate-and-fire, simulação de redes neurais, FastAPI, WebSocket, React,
TypeScript, visualização de grafos.

---

## 15. Créditos e citações

**Linha curta para colocar no fim de um post**

> Dados: FlyWire (Dorkenwald et al., *Nature* 2024; Schlegel et al., *Nature*
> 2024), snapshot v783, uso não comercial (CC-BY-NC 4.0). Explore o dataset em
> codex.flywire.ai.

**Referências do dataset** (detalhes em `data/README.md`)

- Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature*
  634, 124–138 (2024). https://doi.org/10.1038/s41586-024-07558-y
- Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing
  of *Drosophila*. *Nature* 634, 139–152 (2024).
  https://doi.org/10.1038/s41586-024-07686-5
- Eckstein, N. et al. Neurotransmitter classification from electron microscopy
  images at synaptic sites in *Drosophila melanogaster*. *Cell* 187,
  2574–2594 (2024). https://doi.org/10.1016/j.cell.2024.03.016
- Buhmann, J. et al. Automatic detection of synaptic partners in a whole-brain
  *Drosophila* electron microscopy data set. *Nature Methods* 18, 771–774
  (2021). https://doi.org/10.1038/s41592-021-01183-7

**Referências do circuito**

- Seelig, J.D. & Jayaraman, V. *Nature* 521, 186–191 (2015).
  https://doi.org/10.1038/nature14446
- Green, J. et al. *Nature* 546, 101–106 (2017).
  https://doi.org/10.1038/nature22343
- Turner-Evans, D.B. et al. *Neuron* 108, 145–163 (2020).
  https://doi.org/10.1016/j.neuron.2020.08.006
- Hulse, B.K. et al. *eLife* 10, e66039 (2021).
  https://doi.org/10.7554/eLife.66039

**Links úteis**

- Explorador oficial do dataset: https://codex.flywire.ai
- Dump de conectividade: https://doi.org/10.5281/zenodo.10676866

---

## 16. Roadmap e gatilhos de atualização

Próximos passos documentados no README (v1.1) e o post que cada um permitiria:

| Entrega futura | Post que ela permite |
| --- | --- |
| Seletor de política de neurotransmissor na interface | "Veja a diferença que 2 neurônios fazem": comparação lado a lado |
| Destacar na interface os 2 neurônios com sinal invertido | Post visual sobre auditabilidade |
| Segundo circuito: via olfativa (ORNs → lobo antenal → corpo pedunculado) | "Feed-forward × recorrente": contraste com o ring attractor |
| Segundo circuito: detecção de *looming* e fuga (LC4/LPLC2 → neurônio gigante descendente) | "Do estímulo visual à fuga em poucos passos" |
| Streaming do WebSocket fora do event loop principal | Post técnico sobre escalar para circuitos maiores |
| Incluir a normalização por grau de entrada na lista de simplificações | Atualização de honestidade (pequena, mas coerente com o projeto) |
| Demo on-line | Post de relançamento com link clicável |

**Regra:** toda atualização deve manter a frase "conectividade real, dinâmica
simplificada" e atualizar a §4 se algum número mudar.

---

## 17. Conexão com o portfólio

Este é um de três projetos públicos que formam uma narrativa coerente:

| Projeto | Pergunta que responde | Data |
| --- | --- | --- |
| [EEG Signal Processing Lab](https://github.com/jevrton-code/eeg-signal-processing-lab) | Como carregar, inspecionar, pré-processar e analisar EEG de forma responsável? | jun. 2026 |
| [BCI Motor Imagery Classifier](https://github.com/jevrton-code/bci-motor-imagery-classifier) | Dá para classificar imagética motora, e como avaliar isso com honestidade? | jun. 2026 |
| **FlyWire Propagation Sim** (este) | Como a atividade se espalha por um circuito neural real, mapeado sinapse a sinapse? | ago. 2026 |

**O fio condutor:** dados públicos reais, reprodutibilidade, engenharia de
software disciplinada e honestidade sobre os limites. Os dois primeiros
trabalham com o sinal medido no couro cabeludo humano; este vai para o
diagrama de fiação do cérebro e acrescenta o lado de produto (API, interface
e testes de ponta a ponta).

**Post de portfólio possível:** "Três projetos, uma regra: escrever o que o
modelo não faz antes de mostrar o que ele faz."

---

## 18. Pendências encontradas antes de divulgar

1. **Sem arquivo de licença para o código.** Sem `LICENSE`, o código é
   público, mas não é legalmente "open source". Escolha uma licença (por
   exemplo MIT) e lembre que os **dados** continuam CC-BY-NC 4.0.
2. **Nenhuma imagem, GIF ou vídeo do app** no repositório nem no README
   (§10). É a pendência mais importante para o LinkedIn.
3. **Sem demo on-line.** Quem vem do LinkedIn precisaria clonar, instalar
   Python e Node e subir dois servidores.
4. **Tamanho dos dados inconsistente:** o README diz "~370 KB", o
   `data/README.md` diz "~240 KB" e os arquivos somam 251.255 bytes (cerca de
   250 KB).
5. **Versão:** o `pyproject.toml` e o `package.json` dizem `0.1.0`, enquanto o
   README declara a v1 completa. Alinhar para `1.0.0` e criar uma tag/release.
6. **README só em português.** Para alcance internacional, vale um resumo em
   inglês no topo (ou um `README.en.md`).
7. **Sem imagem de *social preview*** configurada no GitHub.

---

## 19. Contexto pessoal a preencher (o que o repositório não sabe)

- **Por que este projeto:** [A PREENCHER]
- **Sua formação e trajetória até aqui:** [A PREENCHER]
- **Tempo dedicado e contexto** (projeto pessoal, curso, transição de
  carreira): [A PREENCHER]
- **O que foi mais difícil ou mais surpreendente:** [A PREENCHER]
- **Ferramentas usadas no processo:** [A PREENCHER]. Observação: o README
  menciona uma revisão final por "`qa-reviewer` + orquestrador", e o
  `.gitignore` ignora arquivos como `CLAUDE.md` e `KICKOFF_PROMPT.md`. Se o
  projeto foi desenvolvido com agentes de IA, decida se e como mencionar isso;
  transparência costuma ser bem recebida, e quem visita o repositório pode
  notar esses sinais.
- **Objetivo profissional** (tipo de vaga, área, empresas de interesse):
  [A PREENCHER]
- **Pessoas ou comunidades para agradecer ou marcar** (por exemplo, a
  comunidade FlyWire): [A PREENCHER]
- **URL do seu perfil no LinkedIn:** [A PREENCHER]

---

## 20. Registro de alterações deste documento

| Data | Alteração |
| --- | --- |
| 2026-10-29 | Versão inicial, cobrindo a v1 (`14d54c8`). Testes Python reexecutados (234 passando); simulação principal reexecutada via CLI (146 de 153 neurônios). Números de front-end e smoke test conforme o README (não reexecutados). |
