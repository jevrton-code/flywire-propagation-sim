# FlyWire Propagation Sim: LinkedIn context document

> **Language:** English · Versão em português: [`CONTEXTO_LINKEDIN.pt-BR.md`](CONTEXTO_LINKEDIN.pt-BR.md)
> **Last updated:** 2026-10-29
> **Project version covered:** v1 (commit `14d54c8`, 2026-08-25)
> **Repository:** https://github.com/jevrton-code/flywire-propagation-sim

---

## 0. What this document is for

This file is the **single source of context** for everything published about
this project on LinkedIn: posts, carousels (PDF document posts), demo videos,
comments, release updates and the profile's "Projects" section. Use it
yourself or hand the whole file to an AI assistant.

Everything here was checked against the repository (code, versioned data,
`data/README.md`, tests and git history) on 2026-10-29. The 234 Python tests
and the headline simulation in §4 were re-run on that date.

**How to use it**

- **To write a post:** read §1 (ready-made summaries), §5 (what the results
  mean) and §6 (what not to claim), then pick an angle from §12.
- **To brief an AI assistant:** give it this file and say which §12 angle you
  want, the language and the length. Tell it to use **only** the numbers in §4
  and to respect §6.
- **When the project changes:** update §4 (fact sheet), §8 (timeline) and §20
  (changelog) first.

**Non-negotiable rules for any public text**

1. The sentence that sums up the project is **"real wiring, toy dynamics"**
   (or "real connectivity, simplified dynamics"). Never call the simulation
   "biologically realistic".
2. Never say the model reproduces the ring-attractor *bump* or predicts fly
   behavior. It doesn't, and the README says so.
3. It is an **engineering portfolio project** built on real scientific data,
   not neuroscience research.
4. Credit FlyWire and the papers (§15). The derived data carries the
   **non-commercial** clause (CC-BY-NC 4.0).
5. The repository **has no license file for the code** yet (§18). Don't say
   "open source" until that's fixed; say "public on GitHub".

---

## 1. Ready-made summaries (shortest to longest)

**One line (bio, video caption, carousel title)**

> A web simulator of neural propagation over a real circuit from the fruit fly
> connectome (FlyWire): real wiring, toy dynamics.

**Hook (fits before "see more")**

> I took a real circuit from a fly's brain, mapped synapse by synapse, and
> built an app to watch activity spread through it. Then I put everything the
> model can't do right on the screen.

**Alternative hook (result)**

> I stimulated 24 neurons in a real 153-neuron circuit. Within two steps,
> activity reached all six cell types; after about 30, the circuit went
> silent.

**Short summary (for a quick post or a comment)**

> I built a web app that simulates neural activity spreading over a real
> circuit from the Drosophila connectome (FlyWire, Nature 2024): the central
> complex compass circuit, with 153 neurons and 2,695 real connections.
> FastAPI back end with WebSocket streaming, React front end and a simple,
> auditable leaky integrate-and-fire model. The wiring is real; the dynamics
> are a caricature, and the app says so on screen.

**Description for the profile's "Projects" section (about 1,650 characters;
LinkedIn limit: 2,000)**

```text
A web app that simulates neural activity spreading over a real circuit from the Drosophila connectome (FlyWire, Nature 2024), with step-by-step interactive visualization.

What I did
• Extracted the central complex compass circuit from FlyWire's public dump (snapshot v783, about 852 MB): 153 neurons and 2,695 real connections, with MD5 checks and a bit-for-bit rebuild verified in the final review.
• Assigned excitatory/inhibitory signs from each neuron's neurotransmitter, following the original paper's rule, and made the disagreements between automatic prediction and literature auditable (148 of 150 neurons agree).
• Implemented a discrete-time leaky integrate-and-fire model that is stable by construction on a graph where 49% of connections are reciprocal.
• Built a FastAPI service with REST endpoints and step-by-step simulation streaming over WebSocket.
• Built a React + Vite front end with three graph layouts, a neuron inspector and an always-visible panel listing the model's 13 simplifications.
• Wrote 234 Python tests, 80 front-end tests and an end-to-end Playwright smoke test.

Result
Stimulating the 24 left-hemisphere EPG neurons recruits 146 of the 153 neurons, across all six cell types; activity reverberates and the circuit falls silent around step 32.

Honest scope: real wiring, toy dynamics. The model shows how activation spreads through the measured connectivity; it does not predict what real neurons do or reproduce the ring-attractor "bump". It is an engineering portfolio project, not neuroscience research.

Stack: Python, NetworkX, NumPy, pandas, FastAPI, WebSocket, React, TypeScript, Vite, pytest, vitest, Playwright.
```

**Suggested "Projects" fields**

| Field | Suggestion |
| --- | --- |
| Project name | FlyWire Propagation Sim: neural propagation over the real Drosophila connectome |
| Date | Aug 2026 (v1 completed 2026-08-25) |
| Skills | Python · FastAPI · React.js · TypeScript · Computational Neuroscience |
| Media | Repository link + app screenshot or video (doesn't exist yet; see §10) |
| Associated with | [TO FILL IN: role, course or "personal project"] |

---

## 2. The problem and the motivation

### In plain words

A **connectome** is the complete map of which neurons connect to which. In
2024 the **FlyWire** consortium published in *Nature* the connectome of an
entire adult fruit fly brain: about 140,000 neurons and 50 million synapses,
reconstructed from electron microscopy images.

This project takes a real piece of that map (the circuit that works as a
**compass** in the fly's brain, tracking head direction) and lets the user
inject a "stimulus" into chosen neurons to watch activation spread through the
real connections, step by step, in a browser.

### Why this circuit

- It is the best-characterized recurrent circuit in the insect brain and the
  textbook example of a biological *ring attractor*.
- It is **strongly recurrent** (49% of connections are part of a reciprocal
  pair), so propagation has structure instead of being a simple cascade.
- It **mixes excitation and inhibition** in an essential way.
- Its expected behavior is published, so anyone can compare the simulation
  with known biology.
- It has the right size: 153 neurons fit in an interactive visualization; the
  whole connectome would not.

### The project's premise

"Engineering precision > biological model sophistication" (README). The value
lies in using real scientific data **correctly and citably**: every number
traceable to its source, every simplification declared.

### Author's personal motivation

[TO FILL IN: why connectomics, what drew you to FlyWire, what you wanted to
learn. See §19.]

---

## 3. What was built

### Architecture

```text
Public sources (no token, no CAVEclient)
  ├─ Zenodo 10.5281/zenodo.10676866 — proofread_connections_783.feather (~852 MB, MD5 checked)
  └─ GitHub flyconnectome/flywire_annotations v2.1.0 — cell types and neurotransmitters
        │
        ▼
flywire_data  (extraction and validation)
  • filters the circuit's 6 cell types; ≥ 5-synapse threshold; sums over neuropils
  • E/I sign from the presynaptic neurotransmitter (Dale's law)
  • fails instead of inventing values; records provenance
        │
        ▼
data/subgraphs/  (versioned in git, ~250 KB of CSV + JSON)
  153 neurons · 2,695 connections · provenance metadata and citations
        │
        ▼
flywire_sim  (model)
  • discrete-time, dimensionless leaky integrate-and-fire, in-degree-normalized weights
  • CLI: python -m flywire_sim.run
        │
        ▼
flywire_api  (FastAPI)
  • REST: /api/health, /api/circuit, /neurons, /edges, /graph, /cell-types, /provenance, /api/model/defaults
  • POST /api/simulations (full run)
  • WS /ws/simulate (one frame per step, as it is computed)
        │
        ▼
frontend  (React + Vite + TypeScript, react-force-graph-2d)
  • 3 layouts: ring by cell type · soma position · force (connectivity)
  • stimulus panel, playback controls, activity timeline
  • neuron inspector, run report
  • always-visible "what this simulator is — and what it isn't" panel
```

### The model, in one sentence

Each neuron holds a membrane variable; on every step it leaks a fraction, adds
the synaptic input from whoever fired on the previous step and, if it crosses a
threshold, the neuron fires, resets and is briefly refractory.

### Why LIF and not a linear model

On a recurrent graph, a linear model (`a[t+1] = leak·a[t] + W·a[t]`) depends
entirely on the spectral radius of `W`: slightly too large and activity
explodes; slightly too small and it dies out. It would have to be tuned right
at the edge of instability, and any change to the data would push it off. In
LIF, each neuron only transmits a binary spike, so the input on every step has
a structural ceiling; with in-degree normalization that ceiling is exactly
`gain`. The state cannot diverge.

### The interface (what's on screen)

- **Three layouts**, each with an honest explanation of what it means:
  - *Ring by cell type* (default): a presentation layout, grouped by
    hemisphere and type; it is **not** the anatomical geometry.
  - *Soma position*: XY projection of the real cell-body coordinates.
  - *Force (connectivity)*: reveals clusters; positions have no anatomical
    meaning.
- **Stimulus panel**: pick neurons by type, hemisphere or ID.
- **WebSocket streaming** with playback controls.
- **Neuron inspector** and **activity timeline**.
- A **display filter** for weak connections (default: ≥ 15 synapses) that
  **never changes the simulation**, only the drawing.
- An always-visible **honesty panel** with the disclaimer and the 13
  simplifications, served directly by the API.
- The UI is in **Portuguese**.

### How to run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m flywire_api.run          # http://127.0.0.1:8000 (Swagger at /docs)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## 4. Fact sheet (verified numbers)

### Data sources

| Item | Value | Source |
| --- | --- | --- |
| Full connectome | ~140,000 neurons, ~50 million synapses (Dorkenwald et al., *Nature* 2024) | `README.md` |
| Connectivity dump | `proofread_connections_783.feather`, 852,022,274 bytes, snapshot v783 | `data/README.md` §2.1 |
| Dump rows before filtering | 16,847,997 | `data/README.md` §2.1 |
| Dump DOI | 10.5281/zenodo.10676866 | `data/README.md` |
| Annotations | `flywire_annotations` v2.1.0 (2024-07-30), 139,255 neurons | `data/README.md` §2.2 |
| Integrity | MD5 checked against the published checksum on every run | `data/README.md` |
| Credentials needed | None (anonymous HTTP access) | `data/README.md` §7 |
| Dump license | CC-BY-4.0 | `data/README.md` §2.3 |
| Annotation license | CC-BY-NC 4.0 (FlyWire Terms of Service); governs the derived product | `data/README.md` §2.3 |

### The subgraph (annotations v2.1.0 + connectivity v783, ≥ 5-synapse threshold)

| Metric | Value |
| --- | --- |
| Neurons | **153** |
| Directed connections | **2,695** |
| Total synapses | 38,141 |
| Reciprocal pairs | 1,328 (49% of connections) |
| Orphan nodes / self-loops | 0 / 0 |
| Synapses per connection (min / median / max) | 5 / 10 / 89 |
| Hemispheres | 77 right, 76 left |
| Main neuropils | PB, EB, NO, GA_L/GA_R |
| Size of the versioned files | about 250 KB (3 files in `data/subgraphs/`) |

### Composition by cell type

| Type | N | Neurotransmitter | Sign |
| --- | ---: | --- | --- |
| EPG | 47 | acetylcholine | excitatory |
| EPGt | 4 | acetylcholine | excitatory |
| PEG | 20 | acetylcholine | excitatory |
| PEN_a (PEN1) | 20 | acetylcholine | excitatory |
| PEN_b (PEN2) | 22 | acetylcholine | excitatory (1 exception in the prediction) |
| Delta7 | 40 | glutamate | inhibitory (1 exception in the prediction) |

### Excitation and inhibition

| Neurotransmitter policy | Neurons E / I / modulatory | Used for |
| --- | --- | --- |
| `predicted` (the paper's automatic prediction) | 113 / 39 / 1 | Versioned dataset |
| `known-first` (literature first) | 113 / 40 / 0 | Simulation and API default |

- Connections under `predicted`: 2,088 excitatory, 585 inhibitory, 22
  modulatory (weight 0, all from a single neuron).
- **Prediction vs literature agreement: 148 of 150 neurons (98.7%).** The 2
  disagreements are among the three lowest-confidence predictions in the set
  (0.354 and 0.402).
- Reported accuracy of the neurotransmitter classifier (Eckstein et al.,
  2024): 87% per synapse and 94% per neuron.

### Annotation version

| Annotations | Neurons | Connections |
| --- | ---: | ---: |
| v2.1.0 (default, the one cited in the 2024 papers) | 153 | 2,695 |
| v3.1.0 | 155 | 2,716 |

The difference is 2 Delta7 neurons. v2.1.0 was chosen for citability.

### Default model parameters (engineering choices, not biological constants)

| Parameter | Value |
| --- | --- |
| `threshold` | 0.20 |
| `leak` | 0.9 per step |
| `refractory_steps` | 3 |
| `gain` | 1.0 |
| Weight normalization | by in-degree (`in-degree`) |
| `noise_std` | 0 (no noise) |
| Max steps per simulation (API) | 500 |
| Concurrent simulations before responding `503` | 4 |

### Headline result (re-run on 2026-10-29)

Command: `python -m flywire_sim.run --source-type EPG --source-side left`
(default parameters, 50 steps).

| Metric | Value |
| --- | --- |
| Stimulated neurons | 24 (every left-hemisphere EPG) |
| Neurons that fired | **146 of 153 (95.4%)** |
| Downstream neurons recruited | 122 |
| Cell types reached | all 6 |
| First spike of downstream types | step 2 |
| Peak | step 6, with 61 neurons firing |
| Last spike | step 31; fully silent from step 32 |
| Total spikes | 785 |
| Numerical state | finite; max membrane \|V\| = 1.0 |

By type: EPG 47/47, EPGt 3/4, PEG 19/20, PEN_a 20/20, PEN_b 22/22,
Delta7 35/40.

### Other documented behaviors (docstring of `model.py`)

- **Stimulating a single EPG is much weaker:** with in-degree normalization,
  one presynaptic partner carries a median 4% of its target's input. 41 of the
  47 EPG recruit at least one direct partner (median 2); 6 recruit none.
- **Saturated regime:** with `refractory_steps` at 0 or 1, or `threshold`
  below about 0.15, the circuit enters a self-sustaining regime. That is the
  expected outcome for a recurrent, isolated, excitation-dominated network
  (113 excitatory vs 40 inhibitory).

### Quality and size

- **Python tests: 234 passing** (data, simulation and API; re-run on
  2026-10-29, about 4 s).
- **Front-end tests: 80** (vitest + Testing Library), per the README.
- **End-to-end smoke test: 26 checks** with Playwright against a real back end
  and dev server, per the README.
- Final review: bit-for-bit rebuild of the subgraph from the original dumps
  and verification of every cited DOI through Crossref.
- 3 Python packages (`flywire_data`, `flywire_sim`, `flywire_api`) and a React
  front end with 8 UI components.

---

## 5. Results and interpretation (the stories the numbers tell)

### 5.1 Real wiring, toy dynamics

The code's own phrase ("*real wiring, toy dynamics*") is the heart of the
message. The project's value is not "simulating a fly's brain"; it is **using
cutting-edge scientific data with engineering rigor** and being explicit about
what the model doesn't do.

### 5.2 A cascade that reaches the whole circuit, then fades

Stimulating the 24 left EPG recruits 95% of the circuit within a few steps,
peaking at step 6, and the circuit goes silent at step 32. It is the app's
strongest visual demonstration.

### 5.3 A single neuron does almost nothing (and that's not a bug)

With in-degree normalization, a single connection carries a median 4% of its
target's input. The difference between stimulating 1 and 24 neurons is a good
story about how **normalization choices change a model's behavior**.

### 5.4 The model doesn't reproduce the bump, and says so

This circuit's real function is to maintain a single "bump" of activity that
tracks head direction. Reproducing it would require tuning the
excitation/inhibition balance far more carefully than a simple, auditable model
should. The app says so on screen.

### 5.5 When automatic prediction disagrees with the literature

The automatic neurotransmitter prediction agrees with the literature for 148
of 150 neurons. The 2 disagreements are exactly among the lowest-confidence
predictions. Instead of "fixing by hand" or hiding it, the project keeps
**both policies** available and exposes exactly where they diverge
(`GET /api/circuit/provenance`).

---

## 6. What you can and cannot say

| ✅ OK to say | ❌ Do not say | Why |
| --- | --- | --- |
| "Simulates activation spreading over real FlyWire connections" | "Simulates the fly's brain" / "biologically realistic" | It is a 153-neuron subcircuit with simplified dynamics. |
| "Real wiring, toy dynamics" | "Predicts what the neurons do" | The model is not calibrated against activity data. |
| "Shows how activation spreads through the measured wiring" | "Reproduces the ring attractor" / "reproduces the bump" | The README explicitly says it doesn't. |
| "One step = one round of synaptic transmission" | "In X milliseconds..." | Time is dimensionless. |
| "An engineering portfolio project built on real scientific data" | "Neuroscience research" / "discovery" | The README defines itself that way. |
| "Public on GitHub" | "Open source" | There is no license file for the code yet. |
| "FlyWire data (Dorkenwald et al., 2024), non-commercial use" | Any suggestion of commercial use of the data | The annotations are CC-BY-NC 4.0. |
| "234 Python tests, 80 front-end tests, an end-to-end smoke test" | "100% coverage" | Coverage was not measured. |
| "I extracted a subgraph from the connectome" | "I mapped the connectome" | The mapping is the FlyWire consortium's work. |

---

## 7. Engineering decisions (behind-the-scenes material)

1. **Fail instead of inventing.** If a source can't be fetched or a
   neurotransmitter isn't recognized, the pipeline raises. There is no silent
   default sign.
2. **Verifiable integrity.** The dump's MD5 is checked against the Zenodo
   checksum on every run; the subgraph was rebuilt bit for bit in the final
   review.
3. **CSV instead of parquet for the subgraph.** The files are small, so CSV
   keeps the data readable and diffable in git, which makes changes auditable.
4. **No credentials.** The MVP uses only public, anonymous sources, with no
   CAVEclient or token.
5. **Citability over 2 extra neurons.** Annotations v2.1.0 (153 neurons)
   instead of v3.1.0 (155), because it is the version cited in the 2024
   *Nature* papers. v3.1.0 is still available through a flag.
6. **Modulatory transmitters weighted 0, explicitly.** Serotonin, dopamine and
   octopamine don't have a sign set by the transmitter; instead of guessing,
   they get weight 0 and are marked `modulatory`.
7. **Two neurotransmitter policies, side by side.** `predicted` (faithful to
   the paper's pipeline) and `known-first` (literature first). The exact
   divergence is exposed through the API.
8. **LIF instead of a linear model.** Stable by construction on a recurrent
   graph, with no tuning at the edge of instability (§3).
9. **Parameters as engineering choices.** `leak`, `threshold` and
   `refractory_steps` were picked by a sweep for stable, legible dynamics, and
   are presented that way; nothing was fitted to biological data.
10. **Honesty travels with the data.** The 13 simplifications are a constant
    in the code (`SIMPLIFICATIONS`), served by the API and shown in the front
    end, instead of living in a docstring.
11. **`root_id` always as a string.** FlyWire IDs have 18 digits and overflow
    JavaScript's largest safe `Number` integer.
12. **Per-neuron values as arrays aligned to the ordering sent in the stream
    header**, for compact WebSocket messages.
13. **Layouts that say what they are.** The ring is labelled as a presentation
    layout, not as anatomy.
14. **Visual filter separate from the simulation.** Hiding weak connections
    changes the drawing, never the computation.
15. **Concurrency limit.** Up to 4 simultaneous simulations; beyond that, the
    API responds `503` instead of degrading.
16. **Extensible architecture.** `flywire_data.circuits` is a circuit
    registry; adding the olfactory pathway or the escape circuit means adding
    an entry.

---

## 8. Timeline

| Time (2026-08-25) | Phase | Commit | What shipped |
| --- | --- | --- | --- |
| 13:24 | — | `5c17a70` | Initial commit: `.gitignore` and project README |
| 14:03 | Phase 1 | `e7a69d9` | Ring attractor subgraph extracted from the real FlyWire data |
| 17:27 | Phase 2 | `0be8753` | Discrete-time LIF model over the graph |
| 17:47 | Phase 3 | `1f2958c` | FastAPI service with REST and WebSocket streaming |
| 23:37 | Phase 4 | `73725bf` | React + Vite front end |
| 23:57 | Phase 5 | `14d54c8` | Final review: v1 readiness gaps closed |

No git tag or GitHub release exists yet (see §18).

---

## 9. Stack and skills

**Back end and data:** Python 3.11+, pandas, pyarrow, NumPy, NetworkX,
FastAPI, Pydantic v2, Uvicorn, WebSocket, pytest, httpx.

**Front end:** React 19, TypeScript, Vite, react-force-graph-2d, vitest,
Testing Library, Playwright.

**Skills to tag on LinkedIn**

- Python
- FastAPI
- React.js
- TypeScript
- WebSockets
- Computational Neuroscience
- Network Science / Graph Theory
- Data Engineering
- Full-Stack Development
- Software Testing

**Skills shown, in recruiter language**

- Taking complex scientific data end to end: extraction, validation, model,
  API and interface.
- Designing APIs with a clear contract (REST + streaming).
- Testing at every layer (unit, API, front end, end to end).
- Treating provenance, licensing and limitations as product requirements.

---

## 10. Visual assets

**There is no image of the app in the repository.** This is the biggest thing
to fix before promoting the project: it is the most visual of the three, and
today a post would have nothing to show.

**Suggested shot list**

| # | What | Suggested format | Use |
| --- | --- | --- | --- |
| 1 | Ring layout at the propagation peak (step 6 of the left-EPG stimulus) | Image, 1080×1350 or 1200×1200 | Main image |
| 2 | Short video (15–30 s) of the propagation, from stimulus to silence | Native video, portrait or square | Launch post |
| 3 | The same stimulus in all three layouts (ring, soma, force) | Carousel | "Honest layouts" post |
| 4 | The "what this simulator is — and what it isn't" panel | Image | Data-honesty post |
| 5 | Neuron inspector showing a `root_id` and its connections | Image | Technical post |
| 6 | API Swagger page (`/docs`) | Image | Back-end post |
| 7 | Activity timeline (spikes per step) | Image | Post about the result (§4) |

**Suggested carousel outline (8 slides, 1080×1350)**

1. Cover: "153 real neurons from a fly, in your browser".
2. What a connectome is and FlyWire (Nature 2024).
3. The compass circuit: cell types and why it was chosen.
4. From an 852 MB dump to a ~250 KB subgraph (MD5-checked pipeline).
5. The model in one sentence + why LIF and not linear.
6. The cascade: 24 stimulated → 146 recruited → silence at step 32.
7. What the simulator is NOT (the simplifications).
8. Stack, tests, GitHub link and credits.

**Also missing:** a GitHub *social preview* image (1280×640) and, ideally, an
online demo (for example a static front end + a hosted API), since most people
won't run the project locally.

---

## 11. Audience, positioning and tone

### Who the posts speak to

| Audience | What they look for | What to highlight |
| --- | --- | --- |
| Recruiters and engineering managers | Ability to ship a complete product | Full stack, multi-layer tests, phased delivery |
| Software engineers (back and front end) | Architecture decisions | WebSocket, API contract, `root_id` as string, concurrency limit |
| Data and science people | Provenance and integrity | MD5, bit-for-bit rebuild, two neurotransmitter policies |
| Computational neuroscience and connectomics | Rigor and domain depth | FlyWire, ring attractor, E/I rule, declared simplifications |
| Curious general public | Watching "a fly's brain" at work | Propagation video, simple explanations |

### Suggested positioning

> Software engineering with real scientific data: from the raw dump to the
> interface, with verifiable provenance and limits declared on screen.

### Tone of voice

- First person, excited about the data, strict about the claims.
- "Real wiring, toy dynamics" should appear in every overview post.
- Avoid "I simulated a brain", "an AI that thinks like a fly" and the like.
- Short paragraphs; few emojis, if any.

### LinkedIn format notes (check them, limits change)

- Post: up to 3,000 characters; the hook must fit in the first lines (about
  200 characters) before "see more".
- "Projects" section description: up to 2,000 characters.
- Native video is the natural format for this project; keep it short and
  captioned, since many people watch without sound.
- Carousel: PDF document post with portrait slides (1080×1350).
- Hashtags: 3 to 5 relevant ones.

---

## 12. Bank of post angles

### A. Launch
- **Hook:** "I took a real circuit from a fly's brain, mapped synapse by synapse,
  and built an app to watch activity spread through it."
- **Points:** FlyWire; 153 neurons and 2,695 real connections; stack; the
  cascade result; "real wiring, toy dynamics".
- **Visual:** propagation video (shot 2 in §10).
- **CTA:** GitHub link; "which circuit would you like to see next?"

### B. The screen that lists what the model can't do
- **Hook:** "The part of my app I'm proudest of is a panel listing 13 things it
  doesn't do."
- **Points:** `SIMPLIFICATIONS` in code → API → front end; honesty that
  travels with the data.
- **Visual:** shot 4.

### C. Why not a linear model
- **Hook:** "The simplest model was unstable. The slightly more complex one was
  stable by construction."
- **Points:** spectral radius; 49% recurrence; LIF's structural ceiling.
- **Audience:** engineering, ML, computational neuroscience.

### D. 18 digits that break JavaScript
- **Hook:** "A neuron ID broke my front end. The fix was to treat it as text."
- **Points:** 18-digit IDs vs `Number`'s safe integer; API contract; aligned
  arrays.
- **Audience:** developers (short, technical post).

### E. From an 852 MB dump to a 250 KB CSV
- **Hook:** "Downloading 852 MB to keep about 250 KB, and being able to prove
  every byte is right."
- **Points:** MD5; fail instead of inventing; bit-for-bit rebuild; diffable
  CSV.
- **Audience:** data.

### F. When AI disagrees with the literature
- **Hook:** "The automatic prediction agreed with the literature on 148 of 150
  neurons. What did I do with the other 2?"
- **Points:** prediction confidence; two policies side by side; nothing
  silently hand-fixed.
- **Audience:** data science, AI.

### G. 2 fewer neurons, a stronger citation
- **Hook:** "I picked the dataset version with fewer neurons. On purpose."
- **Points:** v2.1.0 vs v3.1.0; citability; the other version stays available.

### H. Licenses matter
- **Hook:** "The data is open. That doesn't mean I can do anything with it."
- **Points:** CC-BY-4.0 vs CC-BY-NC 4.0; the most restrictive clause governs.

### I. A single neuron
- **Hook:** "I stimulated one neuron and almost nothing happened. I stimulated
  24 and the whole circuit responded."
- **Points:** in-degree normalization; 4% median; what that says about
  modeling choices.

### J. Testing at every layer
- **Hook:** "234 + 80 + 26: how I tested a neuroscience app end to end."
- **Points:** data, model, API and component tests, plus a Playwright smoke
  test against real servers.
- **Audience:** engineering.

### K. (Optional) How the project was built
- Use only if it makes sense for you (§19). The README mentions a final review
  by "`qa-reviewer` + orchestrator". If the work used AI agents, a post about
  "how I organized the work in phases with strict review" could be a strong,
  transparent angle.

### L. A series with the other projects
- **Hook:** "From the signal on the scalp to the brain's wiring diagram."
- **Points:** link to the EEG and BCI projects (§17).

---

## 13. Glossary for plain-language posts

| Term | Plain explanation |
| --- | --- |
| **Connectome** | The complete map of which neurons connect to which. |
| **FlyWire** | The consortium that reconstructed the connectome of an entire adult fly brain (published in *Nature* in 2024). |
| ***Drosophila melanogaster*** | The fruit fly, one of the most studied organisms in biology. |
| **Synapse** | The contact point where one neuron passes a signal to another. |
| **Neurotransmitter** | The molecule used at the synapse; it helps determine whether the effect is excitatory or inhibitory. |
| **Excitatory / inhibitory** | A connection that raises / lowers the chance the next neuron fires. |
| **Dale's law** | The simplification that each neuron releases a single transmitter at all its outputs. |
| **Ring attractor** | A ring-shaped circuit that keeps a single "bump" of activity; in the fly it works as a compass. |
| **Bump** | A localized group of active neurons whose position on the ring represents direction. |
| **EPG, PEN, PEG, Delta7** | Neuron types in the compass circuit (they carry, shift, feed back and inhibit the bump). |
| **LIF (leaky integrate-and-fire)** | A simple neuron model: it accumulates input, "leaks" over time and fires when it crosses a threshold. |
| **Spectral radius** | A number that says whether activity in a linear model grows or fades over time. |
| **WebSocket** | An open connection between browser and server for sending data in real time. |
| **Snapshot v783** | The frozen version of the connectome used in the 2024 papers. |

---

## 14. Hashtags and keywords

**Hashtags (pick 3 to 5 per post)**

- Core: `#Connectomics` `#ComputationalNeuroscience` `#Python` `#FastAPI`
  `#React`
- Reach: `#Neuroscience` `#OpenScience` `#DataVisualization` `#FullStack`
  `#WebSockets`
- Portuguese-speaking reach: `#Neurociência` `#NeurociênciaComputacional`
  `#DesenvolvimentoWeb`

**Keywords for search and profile SEO:** connectome, FlyWire, Drosophila,
computational neuroscience, ring attractor, leaky integrate-and-fire, neural
network simulation, FastAPI, WebSocket, React, TypeScript, graph
visualization.

---

## 15. Credits and citations

**Short line for the end of a post**

> Data: FlyWire (Dorkenwald et al., *Nature* 2024; Schlegel et al., *Nature*
> 2024), snapshot v783, non-commercial use (CC-BY-NC 4.0). Explore the dataset
> at codex.flywire.ai.

**Dataset references** (details in `data/README.md`)

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

**Circuit references**

- Seelig, J.D. & Jayaraman, V. *Nature* 521, 186–191 (2015).
  https://doi.org/10.1038/nature14446
- Green, J. et al. *Nature* 546, 101–106 (2017).
  https://doi.org/10.1038/nature22343
- Turner-Evans, D.B. et al. *Neuron* 108, 145–163 (2020).
  https://doi.org/10.1016/j.neuron.2020.08.006
- Hulse, B.K. et al. *eLife* 10, e66039 (2021).
  https://doi.org/10.7554/eLife.66039

**Useful links**

- Official dataset explorer: https://codex.flywire.ai
- Connectivity dump: https://doi.org/10.5281/zenodo.10676866

---

## 16. Roadmap and update triggers

Next steps documented in the README (v1.1) and the post each would enable:

| Future delivery | Post it enables |
| --- | --- |
| Neurotransmitter policy selector in the UI | "See the difference 2 neurons make": side-by-side comparison |
| Highlighting the 2 sign-flipped neurons in the UI | Visual post about auditability |
| Second circuit: olfactory pathway (ORNs → antennal lobe → mushroom body) | "Feed-forward vs recurrent": contrast with the ring attractor |
| Second circuit: looming detection and escape (LC4/LPLC2 → giant descending neuron) | "From visual stimulus to escape in a few steps" |
| WebSocket streaming off the main event loop | Technical post about scaling to larger circuits |
| Adding in-degree normalization to the list of simplifications | An honesty update (small, but consistent with the project) |
| Online demo | Relaunch post with a clickable link |

**Rule:** every update should keep the phrase "real wiring, toy dynamics" and
update §4 if any number changes.

---

## 17. How it fits the portfolio

This is one of three public projects that form a coherent story:

| Project | Question it answers | Date |
| --- | --- | --- |
| [EEG Signal Processing Lab](https://github.com/jevrton-code/eeg-signal-processing-lab) | How do you load, inspect, preprocess and analyze EEG responsibly? | Jun 2026 |
| [BCI Motor Imagery Classifier](https://github.com/jevrton-code/bci-motor-imagery-classifier) | Can motor imagery be classified, and how do you evaluate that honestly? | Jun 2026 |
| **FlyWire Propagation Sim** (this one) | How does activity spread through a real neural circuit, mapped synapse by synapse? | Aug 2026 |

**The common thread:** real public data, reproducibility, disciplined software
engineering and honesty about limits. The first two work with the signal
measured on the human scalp; this one moves to the brain's wiring diagram and
adds the product side (API, interface and end-to-end tests).

**Possible portfolio post:** "Three projects, one rule: write down what the
model doesn't do before showing what it does."

---

## 18. Issues to fix before promoting the project

1. **No license file for the code.** Without a `LICENSE`, the code is public
   but not legally "open source". Pick a license (for example MIT) and
   remember the **data** stays CC-BY-NC 4.0.
2. **No image, GIF or video of the app** in the repository or the README
   (§10). This is the most important gap for LinkedIn.
3. **No online demo.** A visitor from LinkedIn would have to clone, install
   Python and Node and start two servers.
4. **Inconsistent data size:** the README says "~370 KB", `data/README.md`
   says "~240 KB" and the files add up to 251,255 bytes (about 250 KB).
5. **Version:** `pyproject.toml` and `package.json` say `0.1.0`, while the
   README declares v1 complete. Align them to `1.0.0` and create a
   tag/release.
6. **README in Portuguese only.** For international reach, add an English
   summary at the top (or a `README.en.md`).
7. **No *social preview* image** set on GitHub.

---

## 19. Personal context to fill in (what the repository can't know)

- **Why this project:** [TO FILL IN]
- **Your background and path so far:** [TO FILL IN]
- **Time invested and context** (personal project, course, career change):
  [TO FILL IN]
- **What was hardest or most surprising:** [TO FILL IN]
- **Tools used along the way:** [TO FILL IN]. Note: the README mentions a
  final review by "`qa-reviewer` + orchestrator", and `.gitignore` ignores
  files such as `CLAUDE.md` and `KICKOFF_PROMPT.md`. If the project was built
  with AI agents, decide whether and how to mention it; transparency tends to
  be well received, and visitors to the repository may notice those signals.
- **Career goal** (type of role, field, companies of interest): [TO FILL IN]
- **People or communities to thank or tag** (for example the FlyWire
  community): [TO FILL IN]
- **Your LinkedIn profile URL:** [TO FILL IN]

---

## 20. Document changelog

| Date | Change |
| --- | --- |
| 2026-10-29 | First version, covering v1 (`14d54c8`). Python tests re-run (234 passing); headline simulation re-run through the CLI (146 of 153 neurons). Front-end and smoke-test numbers as stated in the README (not re-run). |
