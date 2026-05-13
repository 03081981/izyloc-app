#!/usr/bin/env python3
"""
Gerador automatico de post pro blog do izyLAUDO - Push 76 (Fase 2)
==================================================================

Fluxo:
1. Le configuracoes (ecosystem.md, writers/*.md, temas-blog.md)
2. Le posts ja publicados em static/site/blog/posts/
3. Escolhe writer via round-robin (alterna Carlos / Ana / Rafael)
4. Escolhe um tema ainda nao usado da lista
5. Chama Anthropic API (Claude Sonnet 4.5) com prompt rico em contexto
6. Busca imagem na Unsplash baseada na categoria
7. Salva arquivo .md com frontmatter YAML em static/site/blog/posts/

Variaveis de ambiente esperadas:
  ANTHROPIC_API_KEY  - chave da API Anthropic
  UNSPLASH_ACCESS_KEY - access key da Unsplash
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Anthropic SDK e o jeito mais robusto de chamar a API
try:
    from anthropic import Anthropic
except ImportError:
    print("ERRO: pip install anthropic", file=sys.stderr)
    sys.exit(1)

# Requests pra Unsplash
try:
    import requests
except ImportError:
    print("ERRO: pip install requests", file=sys.stderr)
    sys.exit(1)


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
CONFIG_DIR = REPO_ROOT / ".github" / "blog-config"
WRITERS_DIR = CONFIG_DIR / "writers"
POSTS_DIR = REPO_ROOT / "static" / "site" / "blog" / "posts"
USED_THEMES_FILE = REPO_ROOT / "static" / "site" / "blog" / ".used-themes.json"

# Round-robin de writers (ordem dos arquivos = ordem do rodizio)
WRITERS = [
    {"file": "carlos.md", "name": "Carlos Mendes", "role": "Corretor Veterano"},
    {"file": "ana.md", "name": "Ana Cristina", "role": "Advogada Imobiliária"},
    {"file": "rafael.md", "name": "Rafael Torres", "role": "Especialista em Tecnologia Imobiliária"},
]

# Categorias slug -> label
CATEGORIES = {
    "vistoria-imobiliaria": "Vistoria Imobiliária",
    "lei-do-inquilinato": "Lei do Inquilinato",
    "mercado-imobiliario": "Mercado Imobiliário",
    "tecnologia-ia": "Tecnologia e IA",
    "gestao-imobiliaria": "Gestão Imobiliária",
}

# Categoria preferida por writer (writer pega tema da sua categoria primeiro)
WRITER_CATEGORY_PREF = {
    "Carlos Mendes": ["vistoria-imobiliaria", "gestao-imobiliaria", "mercado-imobiliario"],
    "Ana Cristina": ["lei-do-inquilinato", "vistoria-imobiliaria", "gestao-imobiliaria"],
    "Rafael Torres": ["tecnologia-ia", "gestao-imobiliaria", "mercado-imobiliario"],
}

# Unsplash query por categoria (palavras-chave em ingles - mais resultados)
UNSPLASH_QUERY_BY_CATEGORY = {
    "vistoria-imobiliaria": "apartment inspection real estate",
    "lei-do-inquilinato": "lawyer documents contract office",
    "mercado-imobiliario": "real estate keys property handover",
    "tecnologia-ia": "technology laptop modern office",
    "gestao-imobiliaria": "office desk laptop documents",
}

CLAUDE_MODEL = "claude-sonnet-4-5"


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def slugify(text: str) -> str:
    """Converte texto pra slug url-safe."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s\-]", "", text).lower()
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:80]


def br_today():
    """Data de hoje no fuso BRT (UTC-3)."""
    return datetime.now(timezone(timedelta(hours=-3))).date()


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_themes(content: str) -> list[dict]:
    """Le temas-blog.md e retorna lista de {category, theme}."""
    themes = []
    current_cat = None
    cat_label_to_slug = {v: k for k, v in CATEGORIES.items()}
    for line in content.splitlines():
        line = line.strip()
        # Header: ## Categoria: Vistoria Imobiliária (20 temas)
        m = re.match(r"^##\s+Categoria:\s+([^(]+?)\s*\(", line)
        if m:
            label = m.group(1).strip()
            current_cat = cat_label_to_slug.get(label)
            continue
        # Lista: 1. tema...
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m and current_cat:
            themes.append({"category": current_cat, "theme": m.group(1).strip()})
    return themes


def load_used_themes() -> set:
    if not USED_THEMES_FILE.exists():
        return set()
    try:
        data = json.loads(USED_THEMES_FILE.read_text(encoding="utf-8"))
        return set(data.get("used", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_used_themes(used: set):
    USED_THEMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_THEMES_FILE.write_text(
        json.dumps({"used": sorted(used)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_existing_post_slugs() -> list[str]:
    """Lista slugs dos posts existentes."""
    if not POSTS_DIR.exists():
        return []
    slugs = []
    for md in POSTS_DIR.glob("*.md"):
        for line in md.read_text(encoding="utf-8").splitlines()[:30]:
            m = re.match(r'^slug:\s*"?([\w\-]+)"?', line)
            if m:
                slugs.append(m.group(1))
                break
    return slugs


def get_last_authors_in_order(n: int = 3) -> list[str]:
    """Retorna os autores dos ultimos N posts (mais recente primeiro)."""
    if not POSTS_DIR.exists():
        return []
    files = sorted(POSTS_DIR.glob("*.md"), reverse=True)[:n]
    authors = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines()[:30]:
            m = re.match(r'^author:\s*"?(.+?)"?$', line)
            if m:
                authors.append(m.group(1).strip().strip('"'))
                break
    return authors


def pick_writer() -> dict:
    """Round-robin: escolhe writer que NAO escreveu no ultimo post (e idealmente
    nem no anterior). Mantem rotacao mesmo com volume baixo."""
    last_authors = get_last_authors_in_order(n=2)
    print(f"[INFO] Ultimos autores: {last_authors}")
    # Tenta escolher writer que nao esta nos 2 ultimos
    for w in WRITERS:
        if w["name"] not in last_authors:
            return w
    # Fallback: o que nao esta no ultimo
    for w in WRITERS:
        if not last_authors or w["name"] != last_authors[0]:
            return w
    return WRITERS[0]


def pick_theme(writer_name: str, themes: list[dict], used: set) -> dict | None:
    """Escolhe um tema da categoria preferida do writer que ainda nao foi usado."""
    pref_cats = WRITER_CATEGORY_PREF.get(writer_name, list(CATEGORIES.keys()))
    # Primeira passada: respeita ordem de preferencia
    for cat in pref_cats:
        candidates = [t for t in themes if t["category"] == cat and t["theme"] not in used]
        if candidates:
            return candidates[0]
    # Fallback: qualquer tema nao usado
    for t in themes:
        if t["theme"] not in used:
            return t
    return None


def fetch_unsplash_image(query: str, access_key: str) -> dict | None:
    """Busca foto na Unsplash com a query. Retorna {url, alt, credit}."""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 10, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            return None
        # Pega o primeiro com largura suficiente
        for ph in results:
            urls = ph.get("urls", {})
            img_url = urls.get("regular") or urls.get("full")
            if not img_url:
                continue
            # Adiciona params pra optimizar (1200w + auto format)
            if "?" in img_url:
                img_url += "&w=1200&q=80&auto=format"
            else:
                img_url += "?w=1200&q=80&auto=format"
            return {
                "url": img_url,
                "alt": (ph.get("alt_description") or query)[:200],
                "credit_name": ph.get("user", {}).get("name", ""),
                "credit_url": ph.get("user", {}).get("links", {}).get("html", ""),
                "id": ph.get("id"),
            }
        return None
    except Exception as e:
        print(f"[WARN] Unsplash fetch falhou: {e}", file=sys.stderr)
        return None


# -------------------------------------------------------------------
# PROMPT
# -------------------------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = """Voce e um escritor especialista que escreve para o blog do izyLAUDO.

# CONTEXTO DO ECOSSISTEMA

{ecosystem}

# QUEM E VOCE NESSE POST

{writer_persona}

# REGRAS DURAS

1. NUNCA use as frases proibidas listadas no ecossistema
2. NUNCA comece com "Introducao:" ou similar
3. NUNCA termine com resumo generico tipo "esperamos ter ajudado"
4. Escreva em portugues brasileiro natural, conversacional
5. Use markdown valido (## h2, ### h3, **bold**, listas, blockquotes)
6. Inclua o CTA padrao no final do artigo, naturalmente embutido no texto
7. Tom da marca: direto, pratico, sem encheracao
8. Paragrafos curtos (max 4 linhas)
9. Tamanho ideal: 800-1400 palavras

# FORMATO DA RESPOSTA

Voce DEVE responder APENAS com JSON valido, sem texto antes ou depois, no formato:

{{
  "title": "Titulo cativante e SEO-friendly em portugues",
  "summary": "Resumo de 1-2 frases que vai no card do blog (max 220 chars)",
  "content_md": "Conteudo completo do artigo em markdown, sem frontmatter, sem o titulo H1 (o titulo ja vem do campo title acima)",
  "reading_time_min": 7,
  "tags": ["tag1", "tag2", "tag3"]
}}

NAO inclua o titulo H1 dentro do content_md - ele vai ser renderizado separadamente.
Comece o content_md direto com o primeiro paragrafo de texto.
"""


def build_user_message(theme: str, category_label: str) -> str:
    return f"""Escreva um post de blog completo sobre:

**Tema:** {theme}
**Categoria:** {category_label}

Lembre da sua voz e estilo. Inclua exemplos praticos. Foque em valor real pro leitor (corretores, imobiliarias, proprietarios). Termine integrando naturalmente o CTA padrao.

Responda APENAS com o JSON especificado, sem qualquer texto adicional."""


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():
    # 1) Valida env vars
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not anthropic_key:
        print("ERRO: ANTHROPIC_API_KEY nao definida", file=sys.stderr)
        sys.exit(1)
    if not unsplash_key:
        print("ERRO: UNSPLASH_ACCESS_KEY nao definida", file=sys.stderr)
        sys.exit(1)

    # 2) Carrega ecosystem + temas + posts existentes
    ecosystem = read_file(CONFIG_DIR / "ecosystem.md")
    themes_md = read_file(CONFIG_DIR / "temas-blog.md")
    themes = parse_themes(themes_md)
    used_themes = load_used_themes()

    # Marca como usados os temas dos posts ja publicados (em caso de reset)
    existing_slugs = set(list_existing_post_slugs())
    for t in themes:
        if slugify(t["theme"]) in {slugify(s) for s in existing_slugs}:
            used_themes.add(t["theme"])

    print(f"[INFO] Total de temas: {len(themes)} | Usados: {len(used_themes)}")

    # 2.5) Push 78: Auto-expansao se estoque baixo
    # Roda expand-themes.py como subprocess pra evitar duplicar logica.
    # Se expandiu, recarrega temas em memoria pra o resto do fluxo enxergar.
    import subprocess
    available_count = sum(1 for t in themes if t["theme"] not in used_themes)
    if available_count < 20:
        print(f"[INFO] Estoque baixo ({available_count} disponiveis). Acionando expand-themes.py...")
        expand_script = Path(__file__).parent / "expand-themes.py"
        try:
            r = subprocess.run(
                [sys.executable, str(expand_script)],
                env=os.environ.copy(),
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            print(r.stdout)
            if r.stderr:
                print(r.stderr, file=sys.stderr)
            if r.returncode == 0:
                # Recarrega temas (foram expandidos)
                themes_md = read_file(CONFIG_DIR / "temas-blog.md")
                themes = parse_themes(themes_md)
                print(f"[OK] Temas recarregados: {len(themes)} no total")
            else:
                print(f"[WARN] expand-themes.py retornou {r.returncode} — segue com lista atual",
                      file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("[WARN] expand-themes.py timeout — segue com lista atual", file=sys.stderr)

    # 3) Escolhe writer
    writer = pick_writer()
    writer_persona = read_file(WRITERS_DIR / writer["file"])
    print(f"[INFO] Writer escolhido: {writer['name']}")

    # 4) Escolhe tema
    theme = pick_theme(writer["name"], themes, used_themes)
    if not theme:
        # Esgotou - precisa expandir lista
        print("ERRO: todos os temas ja foram usados. Adicione mais em temas-blog.md", file=sys.stderr)
        sys.exit(2)
    cat_label = CATEGORIES.get(theme["category"], theme["category"])
    print(f"[INFO] Tema: '{theme['theme']}' | Categoria: {cat_label}")

    # 5) Chama Claude
    client = Anthropic(api_key=anthropic_key)
    system = SYSTEM_PROMPT_TEMPLATE.format(
        ecosystem=ecosystem,
        writer_persona=writer_persona,
    )
    user_msg = build_user_message(theme["theme"], cat_label)
    print("[INFO] Chamando Claude...")
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw_text = response.content[0].text.strip()

    # Tira eventual cerca de markdown json (```json ... ```)
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        article = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"ERRO: Claude nao retornou JSON valido: {e}", file=sys.stderr)
        print(f"--- RAW ---\n{raw_text[:2000]}\n--- END ---", file=sys.stderr)
        sys.exit(3)

    title = article.get("title", theme["theme"])
    summary = article.get("summary", "")[:220]
    content_md = article.get("content_md", "")
    reading_time = int(article.get("reading_time_min", 6))
    tags = article.get("tags", [])[:5]

    # 6) Imagem Unsplash
    print("[INFO] Buscando imagem Unsplash...")
    img_query = UNSPLASH_QUERY_BY_CATEGORY.get(theme["category"], "real estate")
    img = fetch_unsplash_image(img_query, unsplash_key)
    if not img:
        # Fallback: usa OG default do site
        img = {
            "url": "https://www.izylaudo.com.br/static/site/og-image.jpg",
            "alt": title,
            "credit_name": "",
            "credit_url": "",
        }

    # 7) Monta frontmatter + escreve arquivo
    slug = slugify(title)
    today = br_today()
    filename = f"{today.isoformat()}-{slug}.md"
    filepath = POSTS_DIR / filename

    # Evita duplicar arquivo se um post com mesmo slug existir
    if filepath.exists():
        # Adiciona timestamp pra desambiguar
        ts = datetime.now(timezone(timedelta(hours=-3))).strftime("%H%M")
        filename = f"{today.isoformat()}-{slug}-{ts}.md"
        filepath = POSTS_DIR / filename

    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    # Escape de aspas duplas em campos do frontmatter
    def yaml_str(s):
        return '"' + str(s).replace('"', '\\"').replace('\n', ' ') + '"'

    frontmatter_lines = [
        "---",
        f"title: {yaml_str(title)}",
        f"slug: {yaml_str(slug)}",
        f"author: {yaml_str(writer['name'])}",
        f"author_role: {yaml_str(writer['role'])}",
        f"category: {yaml_str(theme['category'])}",
        f"category_label: {yaml_str(cat_label)}",
        f"date: {yaml_str(today.isoformat())}",
        f"image_url: {yaml_str(img['url'])}",
        f"image_alt: {yaml_str(img['alt'])}",
    ]
    if img.get("credit_name"):
        frontmatter_lines.append(f"image_credit_name: {yaml_str(img['credit_name'])}")
        frontmatter_lines.append(f"image_credit_url: {yaml_str(img['credit_url'])}")
    frontmatter_lines.append(f"summary: {yaml_str(summary)}")
    frontmatter_lines.append(f"reading_time: {reading_time}")
    if tags:
        tags_yaml = "[" + ", ".join(yaml_str(t) for t in tags) + "]"
        frontmatter_lines.append(f"tags: {tags_yaml}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    full_content = "\n".join(frontmatter_lines) + content_md.strip() + "\n"
    filepath.write_text(full_content, encoding="utf-8")
    print(f"[OK] Post salvo: {filepath.relative_to(REPO_ROOT)}")
    print(f"     Titulo: {title}")
    print(f"     Autor: {writer['name']} | Categoria: {cat_label}")
    print(f"     Tamanho: {len(content_md)} chars")

    # 8) Marca tema como usado
    used_themes.add(theme["theme"])
    save_used_themes(used_themes)

    # 9) Output pra GitHub Actions (workflow vai usar pra commit message)
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as gh:
            gh.write(f"post_title={title}\n")
            gh.write(f"post_author={writer['name']}\n")
            gh.write(f"post_filename={filename}\n")


if __name__ == "__main__":
    main()
