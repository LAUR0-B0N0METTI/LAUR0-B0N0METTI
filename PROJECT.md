# Como este card funciona

Reimplementação da técnica usada em [Andrew6rant/Andrew6rant](https://github.com/Andrew6rant/Andrew6rant),
adaptada para ser dirigida por um único arquivo de configuração.

## A ideia central

O card **não é Markdown**. Markdown no GitHub não permite controlar cor por
trecho de texto nem alinhar colunas de forma confiável. A solução é gerar um
**SVG** com fonte monoespaçada, em que cada linha é um `<tspan>` com
`white-space: pre`.

Isso dá três coisas de graça:

1. **Cor por trecho** — `class="key"` (laranja), `class="value"` (azul),
   `class="cc"` (cinza dos pontinhos).
2. **Alinhamento por contagem de caracteres** — como a fonte é monoespaçada,
   basta que `len(prefixo) + len(pontos) + len(valor)` seja **constante** em
   todas as linhas para que as chaves fiquem coladas à esquerda e os valores
   colados à direita. É a técnica de *dot leaders* (sumário de livro).
3. **Tema claro/escuro** — dois arquivos, `dark_mode.svg` e `light_mode.svg`,
   escolhidos pelo `<picture>` do `README.md` via
   `media="(prefers-color-scheme: dark)"`.

O truque do `@font-face` com `size-adjust: 109%` existe para que o avanço
horizontal do fallback (`monospace` do sistema) fique próximo do Consolas,
mantendo a mesma largura de célula (~8.8px a 16px) em Windows, Linux e macOS.

## Arquivos

```
LAUR0-B0N0METTI/
├── .github/workflows/build.yaml   # roda today.py todo dia e commita os SVGs
├── assets/profile.png             # foto de origem da arte ASCII
├── cache/requirements.txt         # PyYAML + Pillow
├── config.yaml                    # ÚNICA fonte de verdade (painel, cores, layout)
├── image_to_ascii.py              # foto -> ascii_art.txt
├── ascii_art.txt                  # arte gerada (versionada; edite à mão se quiser)
├── today.py                       # config + arte -> dark_mode.svg / light_mode.svg
├── dark_mode.svg                  # gerado
├── light_mode.svg                 # gerado
└── README.md                      # só o <picture> apontando para os SVGs
```

## Pipeline

```
assets/profile.png ──image_to_ascii.py──> ascii_art.txt ─┐
                                                          ├─today.py─> *.svg ─> README.md
config.yaml ─────────────────────────────────────────────┘
```

### `image_to_ascii.py`

1. Achata o alpha sobre branco e recorta o fundo uniforme (`autocrop_subject`).
2. Corta parte do busto (`keep_bottom`) e ajusta a proporção (`aspect`).
3. Redimensiona para `cols x rows`, onde
   `cols = rows * (line_height / char_width) * aspect ≈ rows * 2.27 * aspect`.
   Essa razão compensa o fato de a célula de texto ser mais alta que larga.
4. Aplica autocontraste e mapeia o brilho para uma rampa de caracteres.
   Pixels acima de `white_cut` viram espaço — é isso que dá o efeito de
   "recorte" e deixa a silhueta legível.

### `today.py`

1. Lê `config.yaml`.
2. Calcula o `Uptime` (anos/meses/dias desde `uptime.since`, com 🎂 no aniversário).
3. Monta o painel, descobre a largura em caracteres (`max(prefixo+valor) + folga`)
   e preenche o meio de cada linha com pontos até bater a largura.
4. **Garante que a arte ASCII tenha exatamente o mesmo número de linhas do
   painel** — se sobrar, corta; se faltar, centraliza com linhas em branco; se
   o número mudar, regenera a arte na resolução certa.
5. Escreve os dois SVGs com escaping XML (a arte usa `&`, `<`, `>`).

## Customizar

Tudo em `config.yaml`:

- **Adicionar/remover linha do painel**: edite a lista `panel`. A largura, os
  pontinhos e o número de linhas da arte se ajustam sozinhos.
- **Uptime como idade**: troque `uptime.since` pela sua data de nascimento.
- **Textos em português**: `uptime.locale: pt-BR`.
- **Arte mais clara/escura**: mexa em `ascii.white_cut` (menor = mais espaço em
  branco) e `ascii.contrast`.
- **Outro estilo de arte**: `ascii.ramp` aceita `mid`, `long` ou `blocks`.

Depois:

```bash
pip install -r cache/requirements.txt
python today.py          # regenera os dois SVGs
```

Para ver a arte isolada antes de commitar:

```bash
python image_to_ascii.py --rows 24 --white-cut 0.86 --ramp mid
```

## Automação

O workflow roda a cada push na `main`, diariamente às 04:00 UTC e sob demanda
(`workflow_dispatch`). Ele usa o `GITHUB_TOKEN` padrão do Actions com
`permissions: contents: write` — **não é preciso criar nenhum secret**.
