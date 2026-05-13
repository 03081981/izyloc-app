#!/usr/bin/env python3
"""
Auto-expansao de temas do blog izyLAUDO - Push 78
==================================================

Verifica se o estoque de temas disponíveis está baixo (< THRESHOLD).
Se sim, chama o Claude pra gerar TARGET_NEW temas únicos respeitando:
  - distribuicao por categoria
  - sem duplicacao (literal ou semantica) com temas existentes
  - tom da marca + persona-fit

Pode rodar:
  - Standalone via workflow_dispatch
  - Como subprocess do generate-blog-post.py (auto-trigger)

Saida: 0 se OK ou nao precisou expandir, !=0 se falhou.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("ERRO: pip install anthropic", file=sys.stderr)
    sys.exit(10)


# -------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMAS_FILE = REPO_ROOT / ".github" / "blog-config" / "temas-blog.md"
ECOSYSTEM_FILE = REPO_ROOT / ".github" / "blog-config" / "ecosystem.md"
USED_FILE = REPO_ROOT / "static" / "site" / "blog" / ".used-themes.json"

# Triggers
THRESHOLD = 20          # se restam < N temas, expande
TARGET_NEW = 100        # gera N novos temas

# Distribuicao alvo dos temas novos
CATEGORY_DISTRIBUTION = [
    ("vistoria-imobiliaria", "Vistoria Imobiliária", 30),
    ("lei-do-inquilinato",   "Lei do Inquilinato",  20),
    ("mercado-imobiliario",  "Mercado Imobiliário", 20),
    ("tecnologia-ia",        "Tecnologia e IA",     20),
    ("gestao-imobiliaria",   "Gestão Imobiliária",  10),
]
SLUG_TO_LABEL = {slug: label for slug, label, _ in CATEGORY_DISTRIBUTION}

CLAUDE_MODEL = "claude-sonnet-4-5"
# Flag pra forcar expansao mesmo com estoque OK (workflow_dispatch input)
FORCE = os.environ.get("FORCE_EXPAND", "").lower() in ("1", "true", "yes")


# -------------------------------------------------------------------
def parse_existing_themes(content: str) -> list[str]:
    """Retorna lista de strings (so o texto do tema, sem numero)."""
    themes = []
    for line in content.splitlines():
        m = re.match(r"^\d+\.\s+(.+)$", line.strip())
        if m:
            themes.append(m.group(1).strip())
    return themes


def last_theme_number(content: str) -> int:
    n = 0
    for line in content.splitlines():
        m = re.match(r"^(\d+)\.\s+", line.strip())
        if m:
            n = max(n, int(m.group(1)))
    return n


def call_claude_for_themes(api_key: str, ecosystem: str,
                           existing_themes: list[str]) -> list[dict]:
    """Chama Claude e retorna lista de {category, theme}."""
    distrib_str = "\n".join(
        f"- {label} ({slug}): {n} temas"
        for slug, label, n in CATEGORY_DISTRIBUTION
    )
    # Pra prompts longos, lista temas existentes em chunks bem formatados
    existing_str = "\n".join(f"- {t}" for t in existing_themes)

    system = """Voce ajuda o blog do izyLAUDO a expandir sua lista de temas.
O blog publica 2 posts por dia, gerados via IA, com 3 personas: Carlos (corretor veterano),
Ana (advogada imobiliaria) e Rafael (especialista em tech imobiliaria).
Voce gera temas relevantes que ressoam com o publico (corretores, imobiliarias, proprietarios)
e que NAO repetem em conteudo ou em ideia os temas ja existentes."""

    user_msg = f"""# CONTEXTO DA MARCA

{ecosystem}

# TEMAS QUE JA EXISTEM NA LISTA (NAO REPETIR EM CONTEUDO OU IDEIA)

{existing_str}

# TAREFA

Gere EXATAMENTE {TARGET_NEW} temas NOVOS, distribuidos assim:
{distrib_str}

REGRAS DURAS:
1. Cada tema deve ser UNICO e diferente em IDEIA dos existentes (nao so na escrita)
2. Cada tema resolve um problema real ou responde a uma duvida pratica
3. Titulo entre 50 e 90 caracteres, cativante mas direto (estilo: o que o leitor ganha)
4. Sem clickbait barato ("voce nao vai acreditar...")
5. Sem palavras proibidas pelo ecossistema ("no mundo atual", "nos dias de hoje", etc)
6. Distribua os temas tematicos por dificuldade: 30% iniciante, 50% intermediario, 20% avancado
7. Inclua temas de oportunidade sazonal se fizer sentido (chuva, fim de ano, alta temporada)

# FORMATO DA RESPOSTA

Responda APENAS com JSON valido, sem texto antes ou depois:

{{
  "themes": [
    {{"category": "vistoria-imobiliaria", "theme": "Texto do tema aqui"}},
    ...
  ]
}}

Categorias validas (use o slug exato): vistoria-imobiliaria, lei-do-inquilinato,
mercado-imobiliario, tecnologia-ia, gestao-imobiliaria.

Garanta EXATAMENTE {TARGET_NEW} temas e a distribuicao acima."""

    print(f"[INFO] Chamando Claude pra gerar {TARGET_NEW} temas...")
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text.strip()
    # Tira cerca markdown se houver
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERRO: JSON invalido de Claude: {e}", file=sys.stderr)
        print(f"--- RAW (primeiros 1500 chars) ---", file=sys.stderr)
        print(raw[:1500], file=sys.stderr)
        print("--- END ---", file=sys.stderr)
        sys.exit(20)

    themes = data.get("themes", [])
    if not isinstance(themes, list) or not themes:
        print("ERRO: response.themes vazio ou invalido", file=sys.stderr)
        sys.exit(21)

    # Filtra entradas validas
    cleaned = []
    valid_slugs = set(SLUG_TO_LABEL.keys())
    seen_lower = {t.lower() for t in existing_themes}
    for item in themes:
        cat = (item.get("category") or "").strip()
        th = (item.get("theme") or "").strip()
        if not cat or not th:
            continue
        if cat not in valid_slugs:
            print(f"[WARN] categoria invalida '{cat}' - tema descartado: {th[:60]}",
                  file=sys.stderr)
            continue
        if th.lower() in seen_lower:
            print(f"[WARN] tema duplicado literal - descartado: {th[:60]}",
                  file=sys.stderr)
            continue
        cleaned.append({"category": cat, "theme": th})
        seen_lower.add(th.lower())
    return cleaned


def append_themes_to_file(new_themes: list[dict]) -> tuple[int, int]:
    """Agrupa por categoria e anexa no fim do arquivo. Retorna (first_num, last_num)."""
    existing_content = TEMAS_FILE.read_text(encoding="utf-8")
    last_num = last_theme_number(existing_content)

    # Agrupa
    by_cat = {}
    for nt in new_themes:
        by_cat.setdefault(nt["category"], []).append(nt["theme"])

    today = datetime.now().strftime("%Y-%m-%d")
    block = f"\n<!-- ===== EXPANSAO AUTO {today} (+{len(new_themes)} temas) ===== -->\n\n"
    counter = last_num + 1
    first_num = counter

    # Ordem das categorias respeita CATEGORY_DISTRIBUTION
    for slug, label, _ in CATEGORY_DISTRIBUTION:
        themes_in_cat = by_cat.get(slug, [])
        if not themes_in_cat:
            continue
        block += f"## Categoria: {label} ({len(themes_in_cat)} temas)\n\n"
        for t in themes_in_cat:
            block += f"{counter}. {t}\n"
            counter += 1
        block += "\n"

    final_content = existing_content.rstrip() + "\n" + block
    TEMAS_FILE.write_text(final_content, encoding="utf-8")
    return first_num, counter - 1


# -------------------------------------------------------------------
def main():
    # 1) Stock check
    used = set()
    if USED_FILE.exists():
        try:
            used = set(json.loads(USED_FILE.read_text(encoding="utf-8")).get("used", []))
        except json.JSONDecodeError:
            print("[WARN] used-themes.json invalido, considerando vazio")

    existing_content = TEMAS_FILE.read_text(encoding="utf-8")
    existing_themes = parse_existing_themes(existing_content)
    available = [t for t in existing_themes if t not in used]

    print(f"[INFO] Estoque: total={len(existing_themes)} | "
          f"usados={len(used)} | disponiveis={len(available)} | "
          f"threshold={THRESHOLD}")

    if len(available) >= THRESHOLD and not FORCE:
        print(f"[OK] Estoque suficiente (>= {THRESHOLD}). Nao precisa expandir.")
        # GITHUB_OUTPUT pra workflow saber que nao expandiu
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as gh:
                gh.write("expanded=false\n")
                gh.write(f"available={len(available)}\n")
        return 0

    if FORCE:
        print("[INFO] FORCE_EXPAND=true — expandindo independente do estoque")
    else:
        print(f"[WARN] Estoque baixo ({len(available)} < {THRESHOLD}). Expandindo.")

    # 2) Valida env vars
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERRO: ANTHROPIC_API_KEY nao definida", file=sys.stderr)
        return 30

    # 3) Chama Claude
    ecosystem = ECOSYSTEM_FILE.read_text(encoding="utf-8")
    new_themes = call_claude_for_themes(api_key, ecosystem, existing_themes)
    if not new_themes:
        print("ERRO: nenhum tema novo valido apos filtro", file=sys.stderr)
        return 31

    print(f"[OK] {len(new_themes)} temas validos pra anexar")

    # 4) Append no arquivo
    first_num, last_num = append_themes_to_file(new_themes)
    print(f"[OK] {TEMAS_FILE.relative_to(REPO_ROOT)} expandido")
    print(f"     Numeros adicionados: {first_num} a {last_num}")

    # 5) Output pro workflow
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as gh:
            gh.write("expanded=true\n")
            gh.write(f"new_themes_count={len(new_themes)}\n")
            gh.write(f"first_num={first_num}\n")
            gh.write(f"last_num={last_num}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
