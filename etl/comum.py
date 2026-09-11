# -*- coding: utf-8 -*-
"""Utilidades compartilhadas do ETL do Panorama Fiscal (Daddus)."""
import csv, gzip, json, re, unicodedata, io
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "entrada"
DOCS = RAIZ / "docs"
DADOS = DOCS / "dados"
csv.field_size_limit(10**9)

def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)

def num(s):
    """'1.234,56' -> 1234.56 ; None se vazio/inválido."""
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    s = str(s).strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except ValueError: return None

STOP = {"do", "da", "de", "dos", "das", "d"}
def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()

def chave_nome(s):
    """Chave tolerante a grafias: 'Olho d'Água das Cunhãs' == 'Olho da Água das Cunhãs'."""
    s = norm(s).replace("'", " ").replace("-", " ")
    return " ".join(w for w in re.findall(r"[a-z]+", s) if w not in STOP)

def ler_csv(caminho, sep=";", encoding="latin-1", pular=0):
    """Lê CSV do Tesouro (latin-1, ';'), devolve (cabeçalho, linhas)."""
    with open(caminho, encoding=encoding, newline="") as fh:
        txt = fh.read()
    if pular:
        txt = txt.split("\n", pular)[pular]
    rows = [r for r in csv.reader(io.StringIO(txt), delimiter=sep) if r and any(c.strip() for c in r)]
    return [c.strip().strip('"') for c in rows[0]], rows[1:]

def idx(cab, nome, obrigatorio=True):
    alvo = norm(nome)
    for i, c in enumerate(cab):
        if norm(c) == alvo: return i
    if obrigatorio:
        raise KeyError("coluna não encontrada: %r. Cabeçalho: %s" % (nome, cab))
    return -1

def gravar_gz(caminho, obj):
    caminho = Path(caminho); caminho.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(caminho, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    return caminho.stat().st_size

def ler_gz(caminho):
    with gzip.open(caminho, "rt", encoding="utf-8") as fh:
        return json.load(fh)

def mais_recente(pasta, padrao):
    cands = [p for p in Path(pasta).glob("*") if p.is_file() and re.search(padrao, p.name, re.I)]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None
