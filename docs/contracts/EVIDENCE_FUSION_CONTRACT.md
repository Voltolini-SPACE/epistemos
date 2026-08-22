# Contrato arquitetural — Proveniência de evidência e fusão controlada

**Estado**: `E4=CLOSED` · `HEAD=2f536ef` · `WORKTREE=CLEAN` · `PUSH=NO` · `IMPLEMENTATION=BLOCKED_UNTIL_CONTRACT`

Este documento é um **contrato**, não uma especificação. Ele fixa o que qualquer arquitetura de
recuperação híbrida do EPISTEMOS tem de satisfazer, e os critérios pelos quais isso será
verificado. Nenhuma implementação é descrita, nem antecipada.

Foi redigido fora da árvore enquanto estava em rascunho — o gate da missão exigia `WORKTREE=CLEAN`
e nenhum commit, e um contrato ainda não validado não deve sujar o repositório. Agora que está
`FINAL` e auditado contra o código, entra no repositório: um contrato de governança sem
rastreabilidade no Git é um contrato que ninguém consegue provar que estava em vigor.

---

## 0. Registro da correção preservada (requisito 1)

E-4 produziu um resultado negativo e a sua primeira redação o generalizou indevidamente. A
formulação vigente, e a única admissível daqui em diante, é:

> A expansão de consulta **como mecanismo único de ranking**, nas estratégias testadas e neste
> corpus, não produz melhoria adotável.

A formulação antiga — "expansão de consulta é o mecanismo errado" — sobrevive em exatamente dois
lugares, ambos como registro histórico da correção: `docs/benchmarks/E4_SEMANTIC.md:94` e a memória
de E-4. A linha `description` usada para recall foi corrigida e não carrega mais o overclaim.

**Consequência normativa**: este contrato não pode ser lido como fechamento do espaço de projeto.
Ele existe porque uma arquitetura *diferente* ainda não foi testada.

---

## 1. Definições

| Termo | Definição normativa |
|---|---|
| **Espaço de recuperação** | Um mecanismo que, dada uma consulta, produz candidatos ordenados por um score próprio. Dois espaços têm scores incomensuráveis por definição, mesmo que ambos sejam números em [0,1]. |
| **Espaço lexical** | O caminho validado em E-1 a E-3: FTS5 sobre representação persistida, mais o scorer com componentes nomeados. É o único espaço **autoritativo**. |
| **Espaço semântico** | Qualquer mecanismo que proponha candidatos por relação não-lexical. É sempre **candidato**, nunca autoritativo. |
| **Evidência autoritativa** | Aquilo que o sistema afirma ter encontrado. Entra no resultado. |
| **Evidência candidata** | Aquilo que o sistema propõe para consideração. Entra rotulada, nunca no resultado. |
| **Resultado** | A lista que o agente recebe como resposta à consulta. |
| **Apêndice** | Seção estruturalmente separada, posterior ao resultado, contendo evidência candidata rotulada. |
| **Fusão** | A operação que compõe resultado e apêndice numa única resposta. |

A distinção autoritativo × candidato é **estrutural**, não um atributo. Um objeto não "é marcado
como" candidato; ele está no apêndice, e é isso que o torna candidato.

---

## 2. Semântica de fusão adotada (I4 fixado)

**ADOTADA: lista lexical + apêndice semântico rotulado.**

Rejeitadas: intercalação posicional; cotas pré-determinadas.

### Justificativa em termos de auditabilidade e verificabilidade

As três opções satisfazem I4 no mecanismo — nenhuma compara scores entre espaços. Diferem no que a
**saída** permite inferir.

Intercalação e cotas produzem uma lista ordenada única. Nela, a posição lê-se como mérito: um
consumidor que vê o item 3 acima do item 4 infere que o sistema o considera melhor. O sistema
recusa-se a fazer essa comparação, mas a forma da saída a comunica assim mesmo. **Um contrato que
depende de o consumidor não tirar a inferência óbvia é um contrato fraco.**

O apêndice rotulado satisfaz I4 por **ausência**, não por evitação: não existe operação, em ponto
algum, que ordene um candidato lexical contra um semântico. Nenhuma posição do apêndice está acima
de qualquer posição do resultado, porque as duas listas não partilham eixo de ordenação.

Ganhos verificáveis que decorrem da escolha:

- **I6 torna-se estrutural.** A origem de um candidato é determinada pela seção em que está, não
  por um campo que possa estar errado, ausente, ou divergir da realidade.
- **I7 torna-se trivialmente verificável.** Remover o apêndice tem de deixar o resultado
  byte-idêntico. Isto é um teste, não um argumento.
- **I2 torna-se enforçado por construção.** Não há caminho pelo qual evidência candidata entre no
  resultado, porque entrar no resultado é o que significa não ser candidata.
- **A cota desaparece como parâmetro.** Cotas codificam um juízo comparativo ("semântico vale 3
  slots") que ninguém mediu. O apêndice não precisa de tal juízo.

### Custo, declarado

Um candidato semântico altamente relevante fica **abaixo** de um candidato lexical fraco. Não é
efeito colateral: é o preço nomeado pela doutrina, e E-4 mediu o que acontece quando não se paga —
toda categoria que estava em 1,000 regrediu.

Consumidores que queiram um ranking único terão de construí-lo eles próprios, assumindo
explicitamente a comparação que o EPISTEMOS se recusa a fazer. Isso é correto: a comparação passa a
ser uma decisão declarada do consumidor, não um artefato escondido do motor.

---

## 3. Os oito invariantes

Cada invariante tem definição normativa, propriedade exigida, critério objetivo de verificação e
condição de falha. Um invariante sem critério verificável é uma intenção, não um contrato.

### I1 — A evidência lexical permanece autoritativa

- **Definição**: o resultado é produzido exclusivamente pelo espaço lexical.
- **Propriedade**: para toda consulta, o resultado é idêntico ao que o sistema lexical sozinho
  produziria.
- **Verificação**: executar a consulta com a camada semântica ativa e desativada; as listas de
  resultado têm de ser idênticas em conteúdo **e ordem**.
- **Falha**: qualquer divergência, ainda que de ordenação.

### I2 — Evidência semântica nunca se torna autoritativa em silêncio

- **Definição**: nenhum caminho de código promove um candidato do apêndice ao resultado.
- **Propriedade**: promoção só ocorre por ação explícita e registrada de um consumidor, fora do
  motor.
- **Verificação**: teste adversarial em que o espaço semântico devolve, com score máximo, um
  documento que o espaço lexical não encontrou; o documento tem de permanecer no apêndice.
- **Falha**: o documento aparece no resultado.

### I3 — Proveniência preservada por candidato

- **Definição**: todo candidato, em qualquer seção, carrega a origem do espaço, a transformação de
  consulta que o encontrou, e o mecanismo que produziu o seu score.
- **Propriedade**: a proveniência é por candidato, nunca agregada por lista.
- **Verificação**: para toda resposta, todo candidato tem os campos do §4 preenchidos com valores
  não-vazios; nenhum campo aceita o valor "combinado", "misto" ou equivalente.
- **Falha**: um candidato sem origem determinável, ou com origem expressa de forma agregada.

### I4 — Scores de espaços diferentes não são implicitamente comparáveis

- **Definição**: nenhuma operação ordena, soma, normaliza ou compara scores originados em espaços
  distintos.
- **Propriedade**: o score de um candidato só tem significado dentro do seu espaço, e o seu
  espaço é sempre declarado junto dele.
- **Verificação**: auditoria estática — não existe função que receba candidatos de dois espaços e
  devolva ordenação única. Auditoria dinâmica — multiplicar todos os scores semânticos por uma
  constante arbitrária não altera nem o resultado nem a ordem do apêndice.
- **Falha**: a ordem muda sob reescala de um espaço; ou existe caminho que ordena entre espaços.

### I5 — Fusão determinística e explicitamente especificada

- **Definição**: a composição de resultado e apêndice é função pura das duas listas de entrada.
- **Propriedade**: mesma entrada, mesma saída, byte a byte; a regra de desempate dentro do apêndice
  é declarada, como já é no espaço lexical (score DESC, id ASC).
- **Verificação**: cinco execuções idênticas produzem resposta idêntica, incluindo o Receipt; a
  ordem não depende de ordem de inserção, iteração de dicionário, escalonamento ou relógio.
- **Falha**: qualquer variação entre execuções, ou uma regra de desempate não documentada.

### I6 — O Receipt reconstrói o que o agente efetivamente viu — **gate dominante**

- **Definição**: a partir do Receipt isolado, sem acesso ao store, é possível reconstruir a resposta
  completa e, para cada elemento, de onde veio cada componente.
- **Propriedade**: cada candidato é reconstruível quanto a: espaço, autoridade, transformação de
  consulta, mecanismo de score, score, decomposição do score, posição na sua lista, e posição na
  resposta.
- **Verificação**: dado um Receipt, um verificador independente reproduz a resposta e responde às
  seis perguntas do §4 para cada candidato, sem consultar o motor.
- **Falha**: qualquer elemento cuja origem ou posição não seja reconstruível.

> **I6 restringe I4.** Uma semântica de fusão que não permita esta reconstrução é **inadmissível**,
> independentemente de qualidade aparente. A qualidade nunca é avaliada antes deste gate.

### I7 — Ausência de evidência semântica não altera a semântica lexical

- **Definição**: desligar, remover ou nunca instalar a camada semântica não muda o comportamento
  lexical.
- **Propriedade**: o resultado é invariante à presença da camada.
- **Verificação**: a suíte lexical completa executa com a camada ausente e presente-mas-vazia,
  produzindo resultados idênticos; o benchmark E-1/E-3 reproduz os seus números declarados.
- **Falha**: qualquer diferença de métrica ou de ordenação.

### I8 — Falha semântica cai fechada para o caminho lexical

- **Definição**: indisponibilidade, degradação, erro ou timeout do espaço semântico produz apêndice
  vazio, nunca resultado degradado nem erro propagado.
- **Propriedade normativa herdada**: o padrão já estabelecido pelo índice lexical —
  `HEALTHY → DEGRADED → fallback` — com o núcleo não dependendo da integridade da camada (ADR-019).
  Esta herança é deliberada: reusar um invariante já provado por mutação vale mais que inventar
  semântica de degradação nova.
- **Verificação**: injeção de falha em cada modo (ausente, exceção, timeout, resposta malformada);
  em todos, o resultado tem de ser idêntico ao caso sem camada semântica, e o estado de saúde tem
  de ser observável.
- **Falha**: exceção propagada ao chamador; resultado alterado; ou degradação silenciosa sem
  estado observável.

---

## 4. Proveniência por candidato no Receipt

O Receipt vigente sela um ranking com um `lexical_variant` e um `scorer_version` no topo. Isso
deixa de ser suficiente quando existem dois espaços: um campo no topo descreve a resposta inteira e
não distingue os seus elementos.

**Campos por candidato, todos obrigatórios e não-vazios:**

| Campo | Responde a | Domínio |
|---|---|---|
| `space` | qual fonte produziu este candidato | `lexical` \| `semantic` |
| `authority` | era autoritativo ou candidato | `authoritative` \| `candidate` |
| `query_transform` | qual transformação da consulta o encontrou | identificador de regra, ou `identity` |
| `scoring_mechanism` | qual mecanismo produziu o score | identificador versionado |
| `score` + `score_components` | como o score foi composto | já existente |
| `rank_in_space` | posição dentro da sua própria lista | inteiro ≥ 1 |
| `position_in_response` | posição no que o agente viu | inteiro ≥ 1 |

**Campos no topo:**

| Campo | Conteúdo |
|---|---|
| `fusion` | semântica adotada, versão, e os seus parâmetros declarados |
| `spaces` | um registo por espaço participante: identificador, versão, estado de saúde |

**Proibições explícitas.** Nenhum campo pode assumir valor que agregue proveniência: `combinado`,
`misto`, `híbrido`, `vários`, ou omissão tratada como "não se aplica". Se a origem de um candidato
não for determinável, a resposta é inválida — não é um candidato com proveniência desconhecida.

**Determinismo.** O relógio permanece fora do digest, como em E-1. O bloco `fusion` e todos os
campos de proveniência **entram** no digest: duas respostas que diferem em como foram compostas têm
de selar diferentemente, sob pena de o Receipt afirmar equivalência entre coisas distintas.

---

## 5. Fora de escopo, explicitamente

Este contrato **não** autoriza e **não** contém:

- implementação, de qualquer parte;
- alteração do core, incluindo o Receipt vigente;
- commit ou push;
- SPEC, nem antecipação do seu conteúdo;
- escolha de mecanismo semântico concreto — o contrato é indiferente a qual seja, desde que os oito
  invariantes se sustentem;
- qualquer decisão sobre embeddings, modelo, ou dependência;
- reabertura de E-4 ou revisão dos seus números;
- alteração de `docs/brand/**`, que permanece pendência de governança de marca, fora desta linha.

---

## 6. Decisões resolvidas

Ambas as decisões foram resolvidas por decisão humana pelo **caminho conservador**: escolher a
semântica mais custosa em vez de introduzir otimização implícita. `BLOCKED_DECISIONS=0`.

### D1 — Duplicata entre espaços: **não deduplicar**

**Fixado.** Se o mesmo documento for produzido pelo espaço lexical e proposto pelo espaço
semântico, **ambas as ocorrências permanecem**. Não se funde, não se converte a duplicata em score,
rank, anotação ou preferência, e nenhuma das duas ordens é alterada.

A duplicação **é** a informação: representa convergência de dois caminhos independentes de
descoberta, e o consumidor distingue a origem estruturalmente pela seção. É o mesmo princípio pelo
qual duas fontes que afirmam o mesmo são deliberadamente dois claims, não um.

**Invariante D1**: remover uma ocorrência de uma seção não pode alterar a ocorrência independente
da outra seção — nem o seu conteúdo, nem a sua posição, nem o seu score.

**Bateria obrigatória** (a executar quando houver implementação, não antes):

| | Caso | Propriedade exigida |
|---|---|---|
| A | documento só lexical | aparece uma vez, no resultado |
| B | documento só semântico | aparece uma vez, no apêndice |
| C | mesmo documento em ambos | aparece duas vezes, proveniências distintas, ordens intactas |
| D | vários documentos repetidos em ambos | cada par independente; nenhuma ordem alterada |
| E | duplicata com metadata diferente | ambas preservadas verbatim; nenhuma reconciliação |
| F | duplicata com claims/evidence diferentes | ambas preservadas; nenhuma fusão de evidência |

**Consequência derivada — duplicação intra-espaço.** A regra "não fundir ocorrências" é
incondicional. Se o espaço semântico produzir o mesmo documento por duas transformações de consulta
distintas, as duas ocorrências permanecem, distinguidas por `query_transform` (I3). Derivado da
regra fixada, não uma extensão nova.

### D2 — Apêndice e EPCTX: **conta integralmente, omissão sempre declarada**

**Fixado.** O apêndice conta integralmente para o orçamento de tokens e faz parte da saída entregue.
Se o orçamento impedir a sua inclusão integral, o envelope sinaliza `context_incomplete`. A omissão
do apêndice nunca é silenciosa, e nunca é indistinguível da omissão de evidência autoritativa.

**Mecanismo, derivado do que já existe.** O envelope já carrega `incomplete_reasons` — lista
legível por máquina, ordenada e deduplicada, hoje com o vocabulário `history_collapsed`,
`token_limit`, `continuation_available`, `contradiction_unavailable`. A distinção exigida é
expressável por **código de razão distinto**, sem campo novo e sem alterar a semântica vigente:

- omissão de evidência **autoritativa** por orçamento → `token_limit` (significado atual, intacto);
- omissão do **apêndice** por orçamento → código distinto, reservado, nunca `token_limit`;
- ambos omitidos → **ambos os códigos presentes**, o que a lista deduplicada já suporta
  naturalmente.

**Proibição explícita**: o apêndice omitido nunca pode emitir `token_limit`. Reusar o código
tornaria os dois casos indistinguíveis, que é precisamente o que a decisão veda.

**Bateria obrigatória**:

| | Caso | Propriedade exigida |
|---|---|---|
| A | apêndice cabe | `context_incomplete=false`; nenhum código de omissão |
| B | apêndice excede | `context_incomplete=true`; código de apêndice; **nunca** `token_limit` |
| C | autoritativa e apêndice excedem | ambos os códigos presentes e distinguíveis |
| D | só apêndice omitido | código de apêndice presente; `token_limit` ausente |
| E | só autoritativa omitida | `token_limit` presente; código de apêndice ausente |
| F | ambos omitidos | ambos presentes |
| G | orçamento exatamente no limite | inclui; `context_incomplete=false`; determinístico |

---

## 6-bis. Inferências não declaradas encontradas na resolução (§7)

As duas decisões, combinadas, introduzem consequências que nenhuma delas enuncia. Registá-las é o
propósito do §7; deixá-las implícitas reintroduziria exatamente a decisão não-declarada que este
contrato existe para impedir. Ambas são **deriváveis dos invariantes**, não invenções.

### Precedência de empacotamento — derivada de I1 + I2

Se o apêndice conta para o orçamento (D2) e o empacotamento fosse ingénuo, um candidato semântico
poderia **deslocar** evidência autoritativa para fora do envelope. Isso seria evidência candidata a
vencer evidência autoritativa pela inclusão — violação substantiva de I2, ainda que nenhum score
tivesse sido comparado.

**Regra derivada**: a evidência autoritativa é empacotada primeiro e integralmente; o apêndice
consome apenas o remanescente. Um apêndice nunca reduz o que o resultado entrega.

### Numeração de posição por seção — derivada de I4

Se `position_in_response` numerasse continuamente através das seções (resultado 1–10, apêndice
11–15), a posição 11 leria-se como pior que a 10 — exatamente a inferência comparativa que I4 veda,
reintroduzida pela numeração depois de ter sido eliminada pela estrutura.

**Regra derivada**: `position_in_response` é **por seção**. Não existe índice global sobre a
resposta, porque não existe ordenação global.

### Custo duplicado, declarado

D1 mantém as duas ocorrências e D2 faz o apêndice contar integralmente. Logo, um documento presente
nos dois espaços **consome orçamento duas vezes**. É o caminho conservador composto, e é o custo
aceite: nomear a convergência valia mais que economizar o token. Declarado aqui para que não seja
descoberto como surpresa.

---

## 6-ter. Auditoria de consistência contra o código vigente

Executada por leitura do código entregue em `2f536ef`, antes de declarar o contrato final. Objetivo
único: garantir que nenhuma regra recém-fixada contradiga invariante já existente. Seis pontos de
risco verificados, **nenhuma contradição**.

| # | Risco | Verificado em | Resultado |
|---|---|---|---|
| 1 | D1 contradiz o teste de duplicatas? | `tests/unit/test_retrieval_order.py:147` | **Não.** O teste escopa a `eng.search(...)` — a lista lexical. D1 duplica *entre seções*. Compatível. |
| 2 | `position_in_response` contradiz o `rank` selado? | `core/__init__.py:2077` | **Não.** `rank` é `enumerate(results, 1)` sobre uma lista; com uma seção, global e por-seção coincidem. |
| 3 | `incomplete_reasons` admite duas razões? | `context/builder.py:451` | **Sim, nativamente.** É `sorted(set(reasons))`. O caso D2/F sai sem campo novo. |
| 4 | "autoritativa empacota primeiro" contradiz o packer? | `context/builder.py:410-427` | **Não — já é invariante vigente.** Ver abaixo. |
| 5 | I7 contradiz o digest do Receipt? | `core/__init__.py:2099` | **Não.** Ver abaixo. |
| 6 | O envelope admite segunda classe de item? | `context/builder.py:191,248` | **Sim.** `role` + `_ROLE_RANK` já é precedência por classe. Costura compatível. |

### Ponto 4 — a regra derivada reduz-se a um invariante já enforçado

O packer vigente declara e implementa:

> *critical roles (contradiction/current/decision) and pinned contradictions are always kept, **even
> over budget** — the budget can never remove critical evidence.*

A regra derivada em §6-bis ("autoritativa primeiro; apêndice consome o remanescente") **não é nova**:
é uma instância deste invariante. Um item de apêndice, sendo por construção não-autoritativo, nunca
satisfaz a condição `must`, logo nunca desloca evidência autoritativa. A derivação estava certa e o
seu fundamento é mais forte do que eu havia argumentado — está no código, provado, não só deduzido.

**Bónus verificado**: o caso D2/G (orçamento exatamente no limite) já está respondido pelo código
entregue — `used + i.tokens <= effective` inclui o item que cabe exatamente. Não é convenção nova a
fixar; é comportamento vigente a preservar.

### Ponto 5 — I7 é sobre o resultado, não sobre o selo

Se o apêndice integra a resposta e o Receipt sela a resposta, remover o apêndice **altera o
`receipt_hash`**. Isso não contradiz I7 e é obrigatório que assim seja: I7 exige que a *lista de
resultado* seja byte-idêntica, e o Receipt tem de distinguir duas respostas compostas de forma
diferente — selar igual seria afirmar equivalência entre coisas distintas.

**Fixado para evitar leitura errada**: I7 aplica-se à lista de resultado. Não se aplica ao
`receipt_hash`, que **deve** divergir.

### Reconciliação deixada à SPEC (não é contradição)

O Receipt vigente sela `results` — uma lista, com `rank` global — e `result_count`. Uma resposta de
duas seções exige estender essa forma. É **extensão**, não conflito: hoje há uma seção e os dois
esquemas coincidem. A SPEC terá de decidir se `position_in_response` substitui `rank` ou coexiste
com ele; o contrato exige apenas que a numeração seja por seção e que ambas as seções sejam seladas.

---

## 7. Condição de aceitação do contrato

Este contrato está completo quando as duas decisões bloqueadas forem resolvidas por decisão
humana. Até lá:

```
CONTRACT=FINAL
CONSISTENCY_AUDIT=PASS (6 riscos verificados, 0 contradições)
BLOCKED_DECISIONS=0
DUPLICATE_SEMANTICS=EXPLICIT
APPENDIX_EPCTX_SEMANTICS=EXPLICIT
IMPLEMENTATION=NOT_AUTHORISED
SPEC=NOT_AUTHORISED
```

O contrato está resolvido. Isso **não** autoriza SPEC nem implementação: são etapas seguintes, com
autorização própria. As baterias D1/A–F e D2/A–G são obrigações da implementação futura, não
resultados desta etapa — não há o que executar enquanto não houver o que testar.
