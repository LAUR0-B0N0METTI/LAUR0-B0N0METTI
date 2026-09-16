#!/usr/bin/env python3
"""
today.py
--------
Gera `dark_mode.svg` e `light_mode.svg` a partir de `config.yaml` e de
`ascii_art.txt`.

Tecnica (mesma do perfil do Andrew6rant, reimplementada):

*  O card nao e HTML nem Markdown: e um SVG com uma fonte monoespacada.
   Cada linha e um <tspan> com `white-space: pre`, entao o alinhamento e
   controlado contando caracteres, nao pixels.
*  O painel usa "dot leaders": a chave fica colada a esquerda, o valor
   colado a direita e a folga no meio e preenchida com pontos. Como a
   fonte e monoespacada, basta garantir que
   `len(prefixo) + len(pontos) + len(valor)` seja constante em todas as
   linhas para que tudo fique alinhado.
*  Sao gerados dois arquivos (claro/escuro) e o README escolhe um deles
   com `<picture><source media="(prefers-color-scheme: dark)">`.
*  Um GitHub Action roda diariamente para recalcular o campo `Uptime` e
   commitar os SVGs atualizados.

Uso:
    python today.py
"""

import os
import sys
from datetime import date

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ART_FILE = os.path.join(HERE, "ascii_art.txt")

MONTHS_PER_YEAR = 12


# --------------------------------------------------------------------------
# utilitarios
# --------------------------------------------------------------------------
def esc(text):
    """Escapa os caracteres que quebram XML. A arte ASCII usa & e < a vontade."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def plural(value, singular, plural_form):
    return singular if abs(value) == 1 else plural_form


def diff_ymd(start, end):
    """Diferenca calendario entre duas datas, em anos/meses/dias."""
    y = end.year - start.year
    m = end.month - start.month
    d = end.day - start.day
    if d < 0:
        m -= 1
        # dias do mes anterior ao mes final
        prev_month = end.month - 1 or 12
        prev_year = end.year if end.month > 1 else end.year - 1
        if prev_month == 2:
            leap = (prev_year % 4 == 0 and prev_year % 100 != 0) or prev_year % 400 == 0
            days_prev = 29 if leap else 28
        elif prev_month in (1, 3, 5, 7, 8, 10, 12):
            days_prev = 31
        else:
            days_prev = 30
        d += days_prev
    if m < 0:
        y -= 1
        m += MONTHS_PER_YEAR
    return y, m, d


def format_uptime(since, locale="en-US", today=None):
    today = today or date.today()
    y, m, d = diff_ymd(since, today)
    if locale.lower().startswith("pt"):
        words = [
            (y, "ano", "anos"),
            (m, "mes", "meses"),
            (d, "dia", "dias"),
        ]
    else:
        words = [
            (y, "year", "years"),
            (m, "month", "months"),
            (d, "day", "days"),
        ]
    parts = [f"{n} {plural(n, s, p)}" for n, s, p in words]
    text = ", ".join(parts)
    if (since.month, since.day) == (today.month, today.day):
        text += " \N{BIRTHDAY CAKE}"
    return text


# --------------------------------------------------------------------------
# arte ASCII
# --------------------------------------------------------------------------
def load_or_build_art(cfg, rows_needed):
    """Le ascii_art.txt. Se nao existir (ou tiver o numero errado de linhas)
    tenta regerar a partir da foto; se o Pillow nao estiver disponivel,
    centraliza a arte com linhas em branco."""
    art_cfg = cfg.get("ascii") or {}
    lines = None

    if os.path.exists(ART_FILE):
        with open(ART_FILE, "r", encoding="utf-8") as fh:
            lines = fh.read().rstrip("\n").split("\n")

    if lines is None or len(lines) != rows_needed:
        try:
            from image_to_ascii import to_ascii

            lines, _ = to_ascii(
                os.path.join(HERE, art_cfg.get("image", "assets/profile.png")),
                rows=rows_needed,
                aspect=art_cfg.get("aspect", 0.85),
                gamma=art_cfg.get("gamma", 1.0),
                contrast=art_cfg.get("contrast", 1.15),
                white_cut=art_cfg.get("white_cut", 0.86),
                keep_bottom=art_cfg.get("keep_bottom", 0.86),
                ramp=art_cfg.get("ramp", "mid"),
            )
            with open(ART_FILE, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            print(f"-> ascii_art.txt regerado com {rows_needed} linhas")
        except Exception as exc:  # Pillow ausente ou foto faltando
            print(f"!! nao foi possivel regerar a arte ({exc}); ajustando por padding")
            lines = lines or [""]

    # Garantia final: a arte SEMPRE tem o mesmo numero de linhas do painel.
    if len(lines) > rows_needed:
        lines = lines[:rows_needed]
    elif len(lines) < rows_needed:
        missing = rows_needed - len(lines)
        if (art_cfg.get("valign") or "center") == "center":
            top = missing // 2
            lines = [""] * top + lines + [""] * (missing - top)
        else:
            lines = lines + [""] * missing
    return lines


# --------------------------------------------------------------------------
# painel
# --------------------------------------------------------------------------
def rule_head(label):
    """Andrew escreve `andrew@grant -———` mas `- Contact -———`: quando o
    titulo ja termina em hifen o filete emenda direto."""
    return 0 if label.rstrip().endswith("-") else 2


def build_panel(cfg, uptime_text):
    """Devolve (linhas, largura_em_caracteres).

    Cada linha e uma lista de pedacos (texto, classe_css) para virar tspans.
    """
    user = cfg.get("user") or {}
    subs = {
        "handle": user.get("handle", "user"),
        "machine": user.get("machine", "host"),
        "uptime": uptime_text,
    }
    layout = cfg.get("layout") or {}
    min_dots = int(layout.get("min_dots", 4))
    padding = int(layout.get("padding", 6))

    rows = []
    for item in cfg.get("panel") or []:
        if item.get("blank"):
            rows.append(("blank", None, None, None))
        elif "rule" in item:
            rows.append(("rule", item["rule"].format(**subs), None, None))
        else:
            key = str(item["key"])
            value = str(item.get("value", "")).format(**subs)
            rows.append(("kv", key, value, item.get("id")))

    # largura do painel = maior linha + folga, respeitando o minimo de pontos
    widest = 0
    for kind, a, b, _ in rows:
        if kind == "kv":
            widest = max(widest, len(f". {a}:") + min_dots + len(b))
        elif kind == "rule":
            widest = max(widest, len(a) + rule_head(a) + 3 + min_dots)
    width = widest + padding

    out = []
    for kind, a, b, ident in rows:
        if kind == "blank":
            out.append([(". ", "cc", None)])
        elif kind == "rule":
            head = " -" if rule_head(a) else ""
            dashes = width - len(a) - rule_head(a) - 3
            out.append(
                [
                    (a, None, None),
                    (head + "\u2014" * max(dashes, 0) + "-\u2014-", None, None),
                ]
            )
        else:
            prefix = f". {a}:"
            gap = width - len(prefix) - len(b)
            dots = " " + "." * max(gap - 2, 1) + " "
            out.append(
                [
                    (". ", "cc", None),
                    (a, "key", None),
                    (":", None, None),
                    (dots, "cc", f"{ident}_dots" if ident else None),
                    (b, "value", ident),
                ]
            )
    return out, width


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------
SVG_HEAD = """<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{w}px" height="{h}px" font-size="{fs}px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {key};}}
.value {{fill: {value};}}
.cc {{fill: {dots};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{w}px" height="{h}px" fill="{bg}" rx="15"/>
"""


def render_svg(art_lines, panel_lines, panel_width, cfg, palette):
    layout = cfg.get("layout") or {}
    fs = int(layout.get("font_size", 16))
    lh = int(layout.get("line_height", 20))
    cw = float(layout.get("char_width", 8.8))
    margin = int(layout.get("margin", 15))
    gutter = int(layout.get("gutter", 12))

    rows = len(panel_lines)
    art_cols = max((len(l) for l in art_lines), default=0)
    panel_x = int(round(margin + art_cols * cw + gutter))
    # folga extra a direita: os travessoes (U+2014) costumam ser um pouco
    # mais largos que uma celula monoespacada em fontes de fallback.
    width = int(round(panel_x + panel_width * cw + margin + 30))
    height = rows * lh + 30

    parts = [
        SVG_HEAD.format(
            w=width, h=height, fs=fs,
            key=palette["key"], value=palette["value"],
            dots=palette["dots"], bg=palette["background"],
        )
    ]

    # bloco da arte ASCII
    parts.append(f'<text x="{margin}" y="{lh + 10}" fill="{palette["text"]}" class="ascii">\n')
    for i, line in enumerate(art_lines):
        y = lh + 10 + i * lh
        parts.append(f'<tspan x="{margin}" y="{y}">{esc(line)}</tspan>\n')
    parts.append("</text>\n")

    # painel
    parts.append(f'<text x="{panel_x}" y="{lh + 10}" fill="{palette["text"]}">\n')
    for i, chunks in enumerate(panel_lines):
        y = lh + 10 + i * lh
        first = True
        for text, cls, ident in chunks:
            attrs = []
            if first:
                attrs.append(f'x="{panel_x}"')
                attrs.append(f'y="{y}"')
                first = False
            if cls:
                attrs.append(f'class="{cls}"')
            if ident:
                attrs.append(f'id="{ident}"')
            parts.append(f'<tspan {" ".join(attrs)}>{esc(text)}</tspan>')
        parts.append("\n")
    parts.append("</text>\n</svg>\n")
    return "".join(parts)


# --------------------------------------------------------------------------
def main():
    with open(os.path.join(HERE, "config.yaml"), "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    up = cfg.get("uptime") or {}
    since = up.get("since", "2000-01-01")
    if not isinstance(since, date):
        since = date(*[int(x) for x in str(since).split("-")])
    uptime_text = format_uptime(since, up.get("locale", "en-US"))

    panel_lines, panel_width = build_panel(cfg, uptime_text)
    art_lines = load_or_build_art(cfg, len(panel_lines))

    for name, key in (("dark_mode.svg", "dark"), ("light_mode.svg", "light")):
        palette = (cfg.get("theme") or {})[key]
        svg = render_svg(art_lines, panel_lines, panel_width, cfg, palette)
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"-> {name} ({len(panel_lines)} linhas, painel de {panel_width} colunas)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
