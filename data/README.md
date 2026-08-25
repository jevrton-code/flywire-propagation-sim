# Dados: subgrafo do conectoma FlyWire

Este diretório contém o recorte real do conectoma da *Drosophila melanogaster*
usado pela simulação, além do script de extração que o reproduz a partir das
fontes públicas originais.

**Nenhum dado aqui é sintético.** Todos os nós, pesos sinápticos e sinais
excitatório/inibitório vêm de arquivos publicados e versionados do projeto
FlyWire. Se uma fonte não puder ser obtida, o pipeline falha em vez de inventar
valores.

---

## 1. Conteúdo

| Arquivo | Descrição |
| --- | --- |
| `subgraphs/ring_attractor_core_nodes.csv` | 153 neurônios do circuito de bússola do complexo central, com tipo celular, hemisfério, coordenadas de soma, neurotransmissor e sinal E/I. |
| `subgraphs/ring_attractor_core_edges.csv` | 2.695 conexões dirigidas entre esses neurônios, com contagem de sinapses, sinal e peso com sinal. |
| `subgraphs/ring_attractor_core_meta.json` | Proveniência completa, parâmetros de build, contagens e citações, gerado junto com as tabelas. |
| `raw/` | Cache local dos dumps brutos (centenas de MB). **Ignorado pelo git** — é baixado sob demanda. |

Formato escolhido: **CSV**. Os arquivos são pequenos (~240 KB somados), então
CSV é preferível a parquet aqui porque o conteúdo fica legível e diffável no
git, o que permite auditar mudanças no dado ao longo do tempo.

### Colunas de `..._nodes.csv`

| Coluna | Significado |
| --- | --- |
| `root_id` | ID do neurônio no release FlyWire `783` (inteiro de 18 dígitos). |
| `cell_type` | Tipo celular (`EPG`, `EPGt`, `PEN_a(PEN1)`, `PEN_b(PEN2)`, `PEG`, `Delta7`). |
| `cell_type_source` | De qual coluna da tabela de anotações o tipo veio (ver §5). |
| `super_class`, `cell_class` | Hierarquia de anotação (`central` / `CX`). |
| `side` | Hemisfério do soma (`left` / `right`). |
| `soma_x/y/z` | Coordenadas do soma em espaço de voxel 4×4×40 nm (úteis para layout 3D no frontend). |
| `top_nt`, `top_nt_conf` | Neurotransmissor predito por Eckstein et al. (2024) e sua confiança média. |
| `known_nt`, `known_nt_source` | Neurotransmissor estabelecido na literatura, quando existe, e a referência. |
| `known_nt_primary` | Transmissor de molécula pequena extraído de `known_nt`, comparável com `top_nt`. |
| `nt_agrees_with_known` | Se a predição concorda com a literatura (vazio quando não há `known_nt`). |
| `nt_effective` | Transmissor efetivamente usado para atribuir o sinal (ver §6). |
| `nt_source` | Política usada: `predicted` ou `known-first`. |
| `sign` | `+1` excitatório, `-1` inibitório, `0` modulatório. |
| `polarity` | Rótulo textual correspondente a `sign`. |
| `status` | Flag de outlier de segmentação/biologia. Vazio para todos os 153 neurônios (nenhum é outlier). |

### Colunas de `..._edges.csv`

| Coluna | Significado |
| --- | --- |
| `pre_root_id`, `post_root_id` | Neurônio pré e pós-sináptico. |
| `syn_count` | Número de sinapses da conexão, **somado sobre todos os neurópilos**. |
| `sign`, `polarity` | Sinal herdado do neurônio **pré-sináptico** (lei de Dale). |
| `weight` | `sign × syn_count` — peso com sinal, pronto para a simulação. |
| `pre_type`, `post_type` | Tipos celulares, por conveniência. |
| `n_neuropils`, `neuropils` | Em quantos e quais neurópilos a conexão ocorre (`\|`-separados). |

---

## 2. Proveniência

### 2.1 Conectividade

- **Fonte**: FlyWire Whole-brain Connectome Connectivity Data
- **DOI**: [`10.5281/zenodo.10676866`](https://doi.org/10.5281/zenodo.10676866)
  (concept DOI: `10.5281/zenodo.10676865`)
- **Versão**: `783.0` — o snapshot de conectividade v783, o mesmo analisado em
  Dorkenwald et al., *Nature* (2024)
- **Data de publicação**: 2024-06-02
- **Arquivo**: `proofread_connections_783.feather` (852.022.274 bytes,
  MD5 `f48f972d262323a102aed49af1396b8a`)
- **Licença**: **CC-BY-4.0** (declarada nos metadados do registro Zenodo)
- **Data de acesso**: 2026-08-25

O arquivo contém uma linha por tripla (neurônio pré, neurônio pós, neurópilo),
com a contagem de sinapses e as probabilidades médias de cada neurotransmissor.
São 16.847.997 linhas antes de qualquer filtragem.

O MD5 do arquivo baixado é conferido contra o checksum publicado pelo Zenodo a
cada execução; divergência aborta o build.

### 2.2 Anotações (tipos celulares e neurotransmissores)

- **Fonte**: [`flyconnectome/flywire_annotations`](https://github.com/flyconnectome/flywire_annotations)
- **Tag**: [`v2.1.0`](https://github.com/flyconnectome/flywire_annotations/releases/tag/v2.1.0),
  publicada em 2024-07-30
- **Arquivo**: `supplemental_files/Supplemental_file1_neuron_annotations.tsv`
  (MD5 `8527e0a95ed5f112766b13260a91e8e2`, 139.255 neurônios)
- **Data de acesso**: 2026-08-25

A tag `v2.1.0` foi escolhida porque é, segundo as próprias notas de release,
"the version reported on in the Schlegel *et al.*, Nature (2024) and Dorkenwald
*et al.*, Nature (2024)" — ou seja, é a versão de anotações que corresponde ao
snapshot de conectividade v783 usado aqui e aos dois artigos que o projeto cita.
Ver §5 para a comparação com releases mais recentes.

### 2.3 Licenciamento — leia antes de reusar

Duas licenças diferentes incidem sobre este material:

1. O **dump de conectividade** do Zenodo é **CC-BY-4.0**.
2. As **anotações e o proofreading da comunidade FlyWire** são mais restritivos.
   Os [Termos de Serviço do FlyWire](https://flywire.ai/tos) dizem, textualmente:

   > "Your edits and annotations are not considered personal data. You agree that
   > they will be made freely available under a CC-BY-NC 4.0 license, following
   > procedures defined by the community."

Como o subgrafo aqui **embute** as anotações (tipos celulares e
neurotransmissores), a cláusula **não comercial (CC-BY-NC 4.0)** é a mais
restritiva aplicável e portanto governa o produto derivado. Este projeto é um
portfólio não comercial, o que é compatível; um uso comercial exigiria consultar
o FlyWire.

### 2.4 Como citar

```
Dorkenwald, S., Matsliah, A., Sterling, A.R. et al. Neuronal wiring diagram of an
adult brain. Nature 634, 124-138 (2024). https://doi.org/10.1038/s41586-024-07558-y

Schlegel, P., Yin, Y., Bates, A.S. et al. Whole-brain annotation and
multi-connectome cell typing of Drosophila. Nature 634, 139-152 (2024).
https://doi.org/10.1038/s41586-024-07686-5

Eckstein, N., Bates, A.S., Champion, A. et al. Neurotransmitter classification from
electron microscopy images at synaptic sites in Drosophila melanogaster.
Cell 187, 2574-2594 (2024). https://doi.org/10.1016/j.cell.2024.03.016

Buhmann, J., Sheridan, A., Malin-Mayor, C. et al. Automatic detection of synaptic
partners in a whole-brain Drosophila electron microscopy data set.
Nature Methods 18, 771-774 (2021). https://doi.org/10.1038/s41592-021-01183-7
```

---

## 3. Por que este circuito

O recorte é o **núcleo do sistema de direção da cabeça (head-direction) do
complexo central** — o *ring attractor* biológico da mosca.

**Por que este circuito e não outro:**

- É o circuito recorrente mais bem caracterizado do cérebro dos insetos e o
  exemplo canônico de *ring attractor* biológico. Um único "bump" de atividade
  no *ellipsoid body* rastreia a direção da cabeça; neurônios **EPG** carregam o
  bump, **PEN** o deslocam proporcionalmente à velocidade angular, **PEG**
  realimentam, e **Delta7** fornecem a inibição global que mantém exatamente um
  bump vivo.
- Ele é **fortemente recorrente**: 1.328 das 2.695 arestas (49%) fazem parte de
  um par recíproco. Isso importa para o projeto — em um circuito puramente
  feed-forward a "propagação" seria uma cascata trivial; aqui a dinâmica tem
  estrutura.
- Ele **mistura excitação e inibição** de forma funcionalmente essencial, o que
  exercita a regra E/I em vez de deixá-la decorativa.
- O comportamento qualitativo esperado está publicado, então um espectador pode
  comparar a simulação com a biologia conhecida em vez de ter que confiar nela.

**Por que este tamanho:** 153 neurônios e 2.695 arestas cabem confortavelmente em
uma visualização de grafo interativa no navegador e em uma simulação em tempo
real, enquanto o conectoma completo (~140 mil neurônios, ~50 milhões de sinapses)
não caberia. O recorte é grande o suficiente para ter dinâmica não trivial e
pequeno o suficiente para ser inspecionado à mão.

**Referências do circuito** (todas verificadas via Crossref):

- Seelig, J.D. & Jayaraman, V. Neural dynamics for landmark orientation and
  angular path integration. *Nature* 521, 186-191 (2015).
  <https://doi.org/10.1038/nature14446>
- Green, J., Adachi, A., Shah, K.K. et al. A neural circuit architecture for
  angular integration in *Drosophila*. *Nature* 546, 101-106 (2017).
  <https://doi.org/10.1038/nature22343>
- Turner-Evans, D.B., Jensen, K.T., Ali, S. et al. The neuroanatomical
  ultrastructure and function of a biological ring attractor. *Neuron* 108,
  145-163 (2020). <https://doi.org/10.1016/j.neuron.2020.08.006>
- Hulse, B.K., Haberkern, H., Franconville, R. et al. A connectome of the
  *Drosophila* central complex reveals network motifs suitable for flexible
  navigation and context-dependent action selection. *eLife* 10, e66039 (2021).
  <https://doi.org/10.7554/eLife.66039>

---

## 4. Números do subgrafo

Anotações `v2.1.0` + conectividade `v783`, limiar ≥ 5 sinapses:

| Métrica | Valor |
| --- | --- |
| Nós | **153** |
| Arestas dirigidas | **2.695** |
| Sinapses totais | 38.141 |
| Nós órfãos | 0 |
| Pares recíprocos | 1.328 (49% das arestas) |
| Auto-laços | 0 |
| `syn_count` mín / mediana / máx | 5 / 10 / 89 |

**Composição por tipo celular:**

| Tipo | N | Neurotransmissor | Sinal |
| --- | --- | --- | --- |
| `EPG` | 47 | acetilcolina | excitatório |
| `EPGt` | 4 | acetilcolina | excitatório |
| `PEG` | 20 | acetilcolina | excitatório |
| `PEN_a(PEN1)` | 20 | acetilcolina | excitatório |
| `PEN_b(PEN2)` | 22 | acetilcolina | excitatório (1 exceção, ver §6) |
| `Delta7` | 40 | glutamato | inibitório (1 exceção, ver §6) |

**Balanço E/I por neurônio:** 113 excitatórios, 39 inibitórios, 1 modulatório.

**Balanço E/I por aresta:** 2.088 excitatórias, 585 inibitórias, 22 modulatórias
(peso 0).

**Hemisférios:** 77 à direita, 76 à esquerda — o circuito é bilateral, como
esperado.

**Neurópilos das conexões:** predominantemente `PB` (protocerebral bridge), `EB`
(ellipsoid body), `NO` (noduli) e `GA_L`/`GA_R` (gall) — exatamente os
neurópilos do circuito de direção da cabeça, o que serve como verificação
independente de que o recorte pegou o circuito certo.

---

## 5. Decisão: versão das anotações (153 vs. 155 neurônios)

Os tipos do complexo central **mudaram de coluna** entre releases da tabela de
anotações:

- Em **`v2.1.0`**, eles existem apenas na coluna `hemibrain_type` (tipo
  transferido por correspondência com o dataset *hemibrain*); a coluna
  `cell_type` está vazia para a maioria dos neurônios `CX`.
- A partir de **`v3.0.0`** (out/2025), eles foram promovidos para `cell_type`.

Consequência prática:

| Anotações | Nós | Arestas | E / I / mod (arestas) |
| --- | --- | --- | --- |
| `v2.1.0` (padrão) | 153 | 2.695 | 2.088 / 585 / 22 |
| `v3.1.0` | 155 | 2.716 | 2.095 / 599 / 22 |

A diferença é exatamente **2 neurônios `Delta7`** tipados apenas a partir da
comparação com o dataset MaleCNS. O conjunto `v2.1.0` é um **subconjunto estrito**
do `v3.1.0` — nada é incluído a mais ou de forma conflitante, apenas 2 neurônios
a menos.

**Escolhemos `v2.1.0` como padrão** porque é a versão relatada nos dois artigos
da *Nature* de 2024 que o projeto cita e que descrevem o snapshot v783. A
`v3.1.0` depende de Berg et al. (*Cell*, aceito em princípio), uma referência
ainda não publicada formalmente; ganhar 2 neurônios não compensa enfraquecer a
citabilidade. A `v3.1.0` continua disponível via
`--annotations-version v3.1.0` e é resolvida pela mesma lógica de código.

O script registra em `cell_type_source` de qual coluna cada rótulo veio, então a
procedência do tipo de cada neurônio permanece auditável.

---

## 6. Regra excitatório/inibitório e simplificações assumidas

### 6.1 A regra

O sinal de cada conexão é determinado pelo neurotransmissor do neurônio
**pré-sináptico**, seguindo Dorkenwald et al. (2024) textualmente:

> "As a rule, we assume that cholinergic neurons are excitatory and GABAergic and
> glutamatergic neurons are inhibitory."
>
> — Dorkenwald et al., *Nature* 634, 124-138 (2024)

O artigo ampara essa regra em Molina-Obando et al., *eLife* 8, e49373 (2019) e
Liu & Wilson, *PNAS* 110, 10294-10299 (2013).

| Neurotransmissor | Sinal | Peso |
| --- | --- | --- |
| acetilcolina | excitatório | `+syn_count` |
| GABA | inibitório | `−syn_count` |
| glutamato | inibitório | `−syn_count` |
| serotonina, dopamina, octopamina | **modulatório** | `0` |

**Sobre os modulatórios:** o artigo afirma um sinal apenas para os três
transmissores rápidos. Serotonina, dopamina e octopamina são neuromoduladores
cujo efeito pós-sináptico depende do receptor expresso pelo alvo e **não** é
determinado pela identidade do transmissor. Em vez de chutar um sinal, essas
conexões são marcadas explicitamente como `modulatory` e recebem peso 0 — a
suposição fica auditável em vez de escondida. No subgrafo atual isso afeta 22
arestas, todas originadas de um único neurônio.

Um transmissor não reconhecido faz o pipeline **levantar exceção**; não existe
sinal padrão silencioso.

### 6.2 Simplificações e limitações assumidas

1. **Limiar de 5 sinapses.** Pares com menos de 5 sinapses são descartados. É o
   limiar usado em todo o Dorkenwald et al. (2024) — "we use a threshold of five
   synapses to determine a connection between two neurons" — mas os próprios
   autores registram que "the choice of 5 synapses per connection is a reasonable
   but arbitrary one". Conexões fracas reais são perdidas junto com os falsos
   positivos.
2. **Lei de Dale.** Assume-se que cada neurônio libera um único transmissor de
   molécula pequena, e todas as suas saídas recebem o mesmo sinal. O próprio
   artigo nota que co-transmissão ocorre no cérebro da mosca.
3. **Peso = contagem de sinapses.** A força fisiológica da conexão é tratada como
   proporcional ao número anatômico de sinapses. Isso é o que fazem as simulações
   citadas pelo artigo, mas é uma aproximação: a condutância de uma sinapse
   inibitória pode ser ~10× a de uma excitatória, e inibição na mosca pode ser
   *shunting* em vez de subtrativa.
4. **Agregação sobre neurópilos.** Múltiplas linhas (pré, pós, neurópilo) são
   somadas em uma única aresta. A informação de neurópilo é preservada nas
   colunas `neuropils`/`n_neuropils`, mas o peso não a distingue.
5. **Neurotransmissor é predito, não medido.** As predições vêm de Eckstein et
   al. (2024), com acurácia relatada de 87% por sinapse e 94% por neurônio
   (voto majoritário). Predições individuais podem estar erradas.
6. **Circuito isolado do resto do cérebro.** Toda entrada de fora do subgrafo
   (por exemplo dos neurônios em anel `ER`, que trazem a informação visual de
   marco) é ignorada. A simulação modela a dinâmica *interna* do circuito sob um
   estímulo injetado, não o comportamento da mosca.
7. **Sem dinâmica temporal real.** O grafo não carrega atrasos de condução,
   constantes de tempo de membrana ou tipos de receptor.

### 6.3 Concordância com a literatura

150 dos 153 neurônios têm um neurotransmissor **estabelecido na literatura** no
campo `known_nt`, todos atribuídos a Turner-Evans et al. (2020). A predição
automática concorda com a literatura em **148 dos 150** casos (98,7%).

As 2 discordâncias são justamente as **duas predições de menor confiança de todo
o conjunto**:

| `root_id` | Tipo | `top_nt` predito | Confiança | Literatura |
| --- | --- | --- | --- | --- |
| `720575940617752537` | `Delta7` | acetilcolina | 0,354 | glutamato |
| `720575940626306321` | `PEN_b(PEN2)` | serotonina | 0,402 | acetilcolina |

Os 3 neurônios sem `known_nt` são `EPGt` preditos como colinérgicos com
confiança alta (0,89–0,91), consistentes com o quarto `EPGt` e com os `EPG`.

Essas duas discordâncias são **mantidas** no dataset padrão, não corrigidas à
mão: o padrão `--nt-source predicted` reproduz fielmente o que o pipeline
automático do artigo produz. As colunas `known_nt_primary` e
`nt_agrees_with_known` expõem a divergência para quem quiser tratá-la.

Para quem preferir a identidade estabelecida na literatura, o build aceita
`--nt-source known-first`, que resulta em 113 excitatórios / 40 inibitórios /
0 modulatórios — isto é, todos os `Delta7` inibitórios e todo o resto
excitatório, exatamente a arquitetura descrita na literatura do ring attractor.

---

## 7. Reproduzindo

```bash
# a partir da raiz do projeto
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# constrói o subgrafo padrão (baixa ~852 MB do Zenodo na primeira execução)
python -m flywire_data.build_subgraph

# variantes
python -m flywire_data.build_subgraph --annotations-version v3.1.0
python -m flywire_data.build_subgraph --nt-source known-first

# valida o artefato versionado
pytest
```

Os dumps brutos são cacheados em `data/raw/` (ignorado pelo git) e validados por
MD5 contra os checksums publicados. Para reaproveitar um dump que você já tenha
em outro lugar:

```bash
export FLYWIRE_CACHE_DIR=/caminho/para/o/cache
```

O cache espera os nomes `proofread_connections_783.feather` e
`neuron_annotations_<tag>.tsv`.

### Autenticação

**Nenhuma credencial é necessária.** Tanto o registro do Zenodo quanto o
repositório de anotações são públicos e acessíveis por HTTP anônimo, então o MVP
não precisa de CAVEclient nem de token do FlyWire. Um token só seria necessário
para consultar materializações ao vivo via CAVE (por exemplo, versões mais novas
que a v783 ou tabelas ainda não publicadas), o que este projeto não faz.

---

## 8. Próximos circuitos (roadmap)

O módulo `flywire_data.circuits` é um registro de circuitos; adicionar um novo
significa acrescentar uma entrada `Circuit` com seus tipos celulares e a
justificativa. Planejados para fases futuras, **ainda não implementados**:

- **Opção B — via olfativa**: ORNs → neurônios de projeção do lobo antenal →
  corpo pedunculado / chifre lateral. Um circuito majoritariamente feed-forward,
  bom contraste com o ring attractor recorrente.
- **Opção C — detecção de *looming* e fuga**: LC4 / LPLC2 → DNp01 (neurônio
  gigante descendente). Cadeia curta sensório-motora com saída comportamental
  clara.
