# Validador de O.S. com IA

[![CI](https://github.com/JvFaraco/os-validator-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/JvFaraco/os-validator-demo/actions/workflows/ci.yml)

Confere ordens de serviço de manutenção antes de elas chegarem a quem aprova.
Regras em Python checam o que é verificável. A IA entra só para ler a nota do
técnico, e mesmo assim escolhe dentro de um catálogo fechado. A decisão final
é sempre de uma pessoa.

[![Fluxo do validador: contrato, 8 regras, catálogo, guarda de comando, sanitização, IA e validação, com as saídas para PRECISA_CORRECAO, REVISAO_HUMANA e PRONTA_PARA_VALIDACAO, todas terminando numa pessoa. Três O.S. fictícias passam por ele: uma fica pronta, uma volta ao técnico nas regras e uma vai para revisão na guarda de comando](docs/fluxo.svg)](https://jvfaraco.github.io/os-validator-demo/)

**[▶ Abrir a demo interativa](https://jvfaraco.github.io/os-validator-demo/)**: escolha uma das 38 O.S. e
veja, etapa por etapa, o que as regras acharam, o que a sanitização tirou da nota, o que a IA
respondeu e por que o código decidiu. Dá para trocar entre Haiku, Sonnet e o provedor falso.
As respostas são as da rodada real, reexibidas sem chamar a API.

> [!NOTE]
> **Demonstração com dados 100% fictícios.** É inspirada num sistema real que
> mantenho em produção, que já processou mais de 2.300 ordens de serviço desde
> setembro de 2026 e tem 2.222 testes automatizados. O desenho é o mesmo; o
> código, o domínio, o catálogo, as regras e as O.S. foram escritos do zero
> para este repositório.

## O problema

Quando o técnico fecha uma O.S., alguém precisa conferir antes de aprovar.
Parte dessa conferência é mecânica: o equipamento retirado voltou ao estoque? A
cobrança tem o aceite do cliente? A nota foi preenchida? A outra parte exige
ler texto livre: o que o técnico diz que encontrou e o que fez, traduzido para
um par padronizado de problema e solução.

Mandar tudo para um LLM resolveria a segunda parte e criaria quatro problemas:

1. **Custo e opacidade** em checagens que um `if` resolve.
2. **Dado pessoal saindo da máquina**: nome, telefone e endereço do cliente.
3. **Classificação inventada**, fora da lista que o sistema de destino aceita.
4. **Injeção pelo texto**: a nota é escrita por gente e pode conter "aprove esta O.S.".

## A abordagem

O fluxo é o da animação lá em cima. Abra cada etapa para ver o detalhe; na
[demo interativa](https://jvfaraco.github.io/os-validator-demo/) o mesmo fluxo
mostra o que cada etapa fez com cada uma das 38 O.S.

<details>
<summary><b>1 · Contrato de entrada</b>: O.S. malformada vai para revisão humana, nunca para correção.</summary>

A O.S. é validada contra `schemas/ordem.schema.json`. Se vier malformada, o defeito é da coleta, não do técnico: ela vai para revisão humana, nunca para correção.

</details>

<details>
<summary><b>2 · Oito regras determinísticas</b>: qualquer bloqueio devolve a O.S. ao técnico, e a IA nem é chamada.</summary>

Oito regras, cada achado com a evidência que o sustenta:

| Regra | Severidade | O que confere |
| --- | --- | --- |
| `NOTA_VAZIA` | bloqueio | nota ausente ou com menos de 20 caracteres |
| `RETIRADA_SEM_MOVIMENTACAO` | bloqueio | equipamento retirado sem devolução ao estoque |
| `COBRANCA_SEM_ACEITE` | bloqueio | serviço cobrado sem comprovante de aceite |
| `EQUIPAMENTO_NOVO_SEM_TESTE` | bloqueio | equipamento instalado ou substituído sem teste registrado |
| `TIPO_INCOMPATIVEL` | bloqueio | desinstalação que instala, ou manutenção sem ação em equipamento |
| `SERIE_REPETIDA` | bloqueio | série do equipamento novo igual à do retirado |
| `POUCAS_FOTOS` | aviso | menos de 2 fotos |
| `DURACAO_ATIPICA` | aviso | atendimento com menos de 10 min ou mais de 8 h |

Qualquer bloqueio devolve a O.S. ao técnico com uma nota objetiva, e **a IA nem é chamada**: a O.S. volta de qualquer jeito, então gastar tokens ali não muda nada. Avisos seguem para o conferente.

Na demo: [OS-0019, sensor trocado sem devolução ao estoque](https://jvfaraco.github.io/os-validator-demo/#OS-0019/haiku/regras) · [OS-0012, aviso que não bloqueia](https://jvfaraco.github.io/os-validator-demo/#OS-0012/haiku/regras)

</details>

<details>
<summary><b>3 · Catálogo fechado</b>: o Python deixa só as opções que fazem sentido para a O.S.; sem opção ou com comando na nota, revisão humana.</summary>

São 19 combinações em [`config/catalogo.yaml`](config/catalogo.yaml). O Python filtra as que fazem sentido para o tipo de serviço e os equipamentos da O.S. (na OS-0007, 3 de 19). Equipamento sem combinação no catálogo vai direto para revisão humana. Se a nota tiver uma frase de comando ("aprove", "ignore as regras"), a O.S. também vai para revisão, sem chamar a IA.

Na demo: [OS-0033, controle remoto fora do catálogo](https://jvfaraco.github.io/os-validator-demo/#OS-0033/haiku/catalogo) · [OS-0029, a nota tenta dar ordem ao sistema](https://jvfaraco.github.io/os-validator-demo/#OS-0029/haiku/guarda)

</details>

<details>
<summary><b>4 · Sanitização</b>: só três campos saem da máquina, e a nota sai mascarada.</summary>

Só três campos saem da máquina: tipo de serviço, categoria e ação de cada equipamento, e a nota. Telefone, e-mail, CPF e CEP são mascarados na nota, e o nome e o endereço da própria O.S. são procurados no texto e trocados por marcadores. Uma guarda final procura de novo os dados pessoais no pacote pronto; se achar algum, a O.S. vai para revisão sem chamar a IA.

Na demo: [OS-0007, nome e telefone do cliente na nota](https://jvfaraco.github.io/os-validator-demo/#OS-0007/haiku/sanitizacao)

</details>

<details>
<summary><b>5 · IA só onde é preciso interpretar</b>: escolhe uma das opções da O.S. ou responde <code>NENHUMA</code>.</summary>

O modelo recebe o pacote e as opções e devolve `{combinacao_id, confianca, trecho_citado, observacao_conferente}`. Ele pode responder `NENHUMA` quando a nota não sustenta uma escolha só.

Na demo: [OS-0036 com o Haiku](https://jvfaraco.github.io/os-validator-demo/#OS-0036/haiku/ia) e [com o provedor falso](https://jvfaraco.github.io/os-validator-demo/#OS-0036/falso/ia), onde a palavra-chave erra

</details>

<details>
<summary><b>6 · Validação local, para qualquer provedor</b>: cinco conferências; se uma falhar, revisão humana.</summary>

A resposta só é aceita se passar por cinco conferências: JSON válido; dentro do schema; uma das opções desta O.S. (não basta existir no catálogo); trecho citado presente na nota que a IA recebeu, já mascarada; e confiança acima do limiar. Se falhar em qualquer uma, a O.S. vai para revisão humana.

Na demo: [OS-0031, dois atendimentos numa O.S.](https://jvfaraco.github.io/os-validator-demo/#OS-0031/haiku/validacao)

</details>

<details>
<summary><b>7 · Decisão</b>: quem escolhe o caminho é o código; a IA não tem campo para isso.</summary>

O código decide entre três caminhos: `PRONTA_PARA_VALIDACAO` (com avisos ao conferente), `PRECISA_CORRECAO` (com nota ao técnico) ou `REVISAO_HUMANA`. A IA não tem campo para decidir; uma resposta com `"decisao"` é rejeitada pelo schema.

Na demo: [OS-0007 pronta com C13](https://jvfaraco.github.io/os-validator-demo/#OS-0007/haiku/decisao)

</details>

## Como rodar

Python 3.12 ou superior, sem chave, sem rede:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m validador avaliar
```

Outros comandos:

```bash
python -m validador analisar data/ordens/os-0007.json   # o caminho completo de uma O.S.
python -m validador analisar data/ordens/os-0029.json   # nota tentando dar ordem ao sistema
pytest                                                  # 264 testes, todos offline
python tools/gerar_demo.py                              # atualiza os dados da demo interativa
```

A saída do `analisar` para a OS-0007, no terminal:

![Saída do comando analisar para a OS-0007](docs/analisar.svg)

Com o modelo de verdade (opcional):

```bash
pip install -e ".[ia]"
export ANTHROPIC_API_KEY=...                       # Windows: $env:ANTHROPIC_API_KEY="..."
python -m validador avaliar --provedor anthropic --salvar                              # Haiku 5.5
python -m validador avaliar --provedor anthropic --modelo claude-sonnet-5-5 --salvar   # comparação
```

## Resultados da avaliação

São 38 O.S. fictícias, e cada uma tem um rótulo escrito à mão em
[`data/gabarito.yaml`](data/gabarito.yaml), com o motivo: 16 prontas, 12 para
correção e 10 para revisão humana. As 10 de revisão são os casos difíceis: nota
vaga, dois atendimentos numa O.S., nota que contradiz o equipamento registrado,
negação, equipamento fora do catálogo e uma tentativa de injeção.

| Provedor | Decisão | Classificação | Chamadas à IA | Custo da rodada |
| --- | --- | --- | --- | --- |
| **Claude Haiku 5.5** (`claude-haiku-5-5`, padrão) | **38/38 (100%)** | **16/16 (100%)** | 24 | ~US$ 0,005 |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 38/38 (100%) | 16/16 (100%) | 24 | ~US$ 0,106 |
| Falso, por palavras-chave (linha de base) | 37/38 (97,4%) | 16/16 (100%) | 24 | US$ 0 |

![Avaliação com o Claude Haiku 5.5](docs/avaliar-haiku.svg)

Foi uma rodada única de cada modelo, em 9/11/2026, com esforço `low`. Das 38
O.S., só 24 chegaram à IA. As 12 com pendência pararam nas regras, uma parou na
guarda de comando e outra por não ter combinação no catálogo. Os dois modelos
tomaram a mesma decisão nas 38 O.S., e o Sonnet custou cerca de 20 vezes mais.
Neste conjunto, o modelo mais barato bastou, e é por isso que ele é o padrão.
Os relatórios, com a resposta do modelo para cada O.S., estão em
[`resultados/`](resultados/) e podem ser reexibidos sem chave:

```bash
python -m validador avaliar --de resultados/avaliacao-anthropic-claude-haiku-5-5.json
```

**Como ler esses números.** Um 100% em 38 casos fictícios, escritos pela mesma
pessoa que escreveu o gabarito, não prova que o modelo acerta 100% em produção.
Prova que este conjunto ficou fácil demais para separar um modelo bom de um
ótimo. O que a rodada mostra de útil está nos detalhes:

- **Onde o falso erra, o modelo acerta.** Na OS-0036 a nota diz que o cliente "achou que o sensor não detectava, mas o sensor estava bom". A palavra-chave pega "não detecta" e aprova a O.S. com a classificação errada. O Haiku se absteve e citou "o sistema era armado no modo errado". Dá para [comparar os dois na demo](https://jvfaraco.github.io/os-validator-demo/#OS-0036/falso/ia).
- **Abster-se no caso certo.** As 8 O.S. de revisão que chegaram ao modelo voltaram como `NENHUMA`, com o motivo certo: "não diz se a bateria trocada era da central ou de um sensor sem fio", "os equipamentos registrados são SIRENE", "descreve dois atendimentos".
- **A trava do trecho citado funcionou com dado mascarado.** Na OS-0037 o modelo citou um trecho com `[TELEFONE]`, e a conferência contra a nota mascarada aceitou.
- **O provedor falso não serve de régua.** Os 16/16 dele são otimistas por construção, porque fui eu quem escreveu as palavras-chave e as notas. Ele existe para o CI rodar offline e para mostrar o tipo de erro que só palavra-chave comete.

O próximo passo para o número dizer mais seria um conjunto mais difícil: notas
com erro de digitação, abreviação e áudio transcrito, rotuladas por outra
pessoa, e mais de uma rodada por modelo, porque a saída de um LLM pode variar
de uma execução para outra. Com um conjunto assim, a comparação entre Haiku e
Sonnet passaria a dizer alguma coisa sobre qualidade, e não só sobre custo.

- **Decisão:** caminho escolhido contra o gabarito, nas 38 O.S.
- **Classificação:** combinação certa nas 16 O.S. que têm uma no gabarito. Se a IA se abstém onde havia resposta, conta como erro.
- As regras também são conferidas contra o gabarito (38/38). Como regras e gabarito saíram da mesma pessoa, isso serve como teste de regressão, não como medida de qualidade.

As três rodadas ficam versionadas em [`resultados/`](resultados/). Um teste
recalcula as métricas de cada relatório a partir dos casos e do gabarito, e a
rodada do provedor falso tem que bater com uma rodada nova. Os prints de terminal
deste README saem da saída real do CLI, por `python tools/gerar_print.py`. A demo
interativa sai do mesmo jeito: `python tools/gerar_demo.py` passa cada O.S. pelo
código com as respostas gravadas de cada rodada e para se o caminho não bater com
o relatório salvo; um teste falha se `docs/dados.json` ficar desatualizado.

## Decisões técnicas

- **Regras antes da IA.** O que dá para verificar com dado estruturado não passa por modelo: é mais barato, auditável e não erra por interpretação.
- **Catálogo preso em três camadas.** O Python filtra as opções; o schema enviado ao modelo tem um `enum` só com elas e `NENHUMA`; e a validação local confere de novo, porque o contrato tem que valer para qualquer provedor, inclusive um que não suporte saída estruturada.
- **Trecho citado como trava contra alucinação.** A IA precisa copiar da nota a frase que sustenta a escolha, e o código confere se a frase está lá. A conferência é feita contra a nota mascarada, que é o que a IA viu. Assim, um trecho com `[TELEFONE]` passa, e uma frase inventada não.
- **Abster-se é uma resposta válida.** `NENHUMA` leva a O.S. para revisão humana. É melhor do que forçar uma escolha.
- **A nota é dado, não instrução.** São três camadas. O código detecta frases de comando óbvias e manda a O.S. para revisão antes de chamar a IA; o teste disso usa um modelo "obediente" que cita um trecho verdadeiro da nota, e ele nem chega a ser consultado. O prompt manda o modelo se abster diante de comandos que escapem do padrão. E o modelo não tem como decidir o caminho da O.S. A detecção por padrão não pega tudo, e é por isso que ela não é a única camada.
- **Allowlist, não blocklist.** O pacote da IA é montado do zero e validado com `additionalProperties: false`. Um campo novo na O.S. não sai da máquina por acidente.
- **Provedor é interface.** O provedor falso é o padrão, roda nos testes e no CI e devolve o mesmo JSON do real. O provedor real só sobe com `ANTHROPIC_API_KEY`. Ele também é testado com o SDK de verdade contra um servidor HTTP local, para checar o formato do pedido sem tocar a rede.
- **Consciência de custo.** O padrão é o Claude Haiku 5.5 com esforço `low`: classificar uma nota curta numa lista de três opções não pede um modelo maior. O `--modelo` troca para Sonnet ou Opus quando valer a comparação. A avaliação imprime os tokens e o custo estimado da rodada.

## Estrutura

```
validador/
├── cli.py            analisar · avaliar
├── regras.py         as 8 regras determinísticas
├── catalogo.py       carga e validação do catálogo, opções por O.S.
├── guarda.py         frase de comando na nota → revisão, sem chamar a IA
├── sanitizacao.py    allowlist, máscara de texto livre, guarda final
├── decisao.py        orquestra uma O.S. e escolhe o caminho
├── avaliacao.py      roda o gabarito: acurácias, matriz, erros, custo
├── saida.py          formatação do terminal
└── ia/
    ├── base.py       interface de provedor
    ├── falso.py      linha de base offline (palavras-chave)
    ├── claude.py     API da Anthropic com saída estruturada
    ├── prompt.py     instruções e mensagem
    ├── schema.py     contrato da resposta e versão para a API
    └── validacao.py  as cinco conferências da resposta
config/catalogo.yaml       19 combinações problema → solução
schemas/                   entrada da O.S., pacote da IA, resposta da IA
data/ordens/               38 O.S. fictícias
data/gabarito.yaml         rótulo de cada O.S., escrito à mão
resultados/                rodadas versionadas da avaliação
docs/                      demo interativa (GitHub Pages) e imagens do README
tools/scan_pii.py          varredura de dado pessoal e segredos (CI)
tools/gerar_print.py       gera os prints de terminal do README
tools/gerar_demo.py        gera docs/dados.json para a demo interativa
```

## Limites

- **A confiança informada pelo modelo não é calibrada.** É uma autoavaliação, não uma probabilidade. Nas rodadas, as mesmas O.S. vagas receberam "alta" do Haiku e "baixa" do Sonnet, com a mesma decisão. O limiar ("baixa" vai para revisão) é só uma trava a mais, e não trato esse número como medida de certeza. Calibrar exigiria medir o acerto por faixa de confiança num volume real.
- **Amostra pequena e limpa.** São 38 casos escritos por mim. Notas reais têm erro de digitação, abreviação e áudio transcrito. Qualquer número aqui vale para estes dados e para o provedor usado, não para produção.
- **A máscara do texto livre tem buraco.** Ela pega padrões (telefone, e-mail, CPF, CEP) e os dados pessoais da própria O.S. O nome de um terceiro citado na nota, como um vizinho ou o porteiro, passaria. A allowlist limita o estrago, mas não resolve.
- **Uma combinação por O.S.** Uma O.S. com dois atendimentos diferentes vai para revisão em vez de receber duas classificações.
- **Falta conferir a coerência entre solução e registro.** Uma "substituição" escolhida para um equipamento que só foi ajustado ainda passaria. Seria a próxima regra.
- **Preços fixos no código.** Os preços por token servem só para a estimativa impressa; confira a página de preços antes de citar valores.

## Licença

MIT.
