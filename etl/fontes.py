# -*- coding: utf-8 -*-
"""
Baixa as bases brutas do Tesouro Nacional para a pasta entrada/.
Toda função devolve o caminho do arquivo salvo ou None (falha). O orquestrador
(atualizar.py) usa o arquivo manual mais recente em entrada/ quando o download falha.
"""
import json, re, time
from datetime import date
from pathlib import Path
import requests
from comum import ENTRADA, log

CKAN = "https://www.tesourotransparente.gov.br/ckan/api/3/action/"
UA = {"User-Agent": "Mozilla/5.0 (painel-fiscal-daddus; +https://daddusconsultoria.com)"}
HOJE = date.today().strftime("%Y%m%d")

def _get(url, **kw):
    for tent in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 120), **kw)
            if r.status_code == 200: return r
            log("  HTTP", r.status_code, url)
        except requests.RequestException as e:
            log("  falha de rede:", e)
        time.sleep(3 * (tent + 1))
    return None

def _baixar(url, destino):
    r = _get(url, stream=True, timeout=600)
    if not r: return None
    destino = Path(destino); destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as fh:
        for chunk in r.iter_content(1 << 20): fh.write(chunk)
    log("  salvo", destino.name, round(destino.stat().st_size / 1e6, 1), "MB")
    return destino

def ckan_pacote(id_ou_slug):
    r = _get(CKAN + "package_show", params={"id": id_ou_slug})
    if not r: return None
    j = r.json()
    return j["result"] if j.get("success") else None

def ckan_busca(texto):
    r = _get(CKAN + "package_search", params={"q": texto, "rows": 20})
    return r.json()["result"]["results"] if r else []

def _recurso_mais_novo(recursos, padrao_nome, formatos=("csv", "xlsx")):
    c = [x for x in recursos if (x.get("format") or "").lower() in formatos and re.search(padrao_nome, (x.get("name") or "") + " " + (x.get("url") or ""), re.I)]
    if not c: return None
    return max(c, key=lambda x: x.get("last_modified") or x.get("created") or "")

# ------------------------------------------------------------------ CAPAG (anual, xlsx)
def capag():
    log("CAPAG: consultando o CKAN (dataset capag-municipios)")
    p = ckan_pacote("capag-municipios")
    if not p: return None
    rec = _recurso_mais_novo(p["resources"], r"capag.*munic", ("xlsx",))
    if not rec: log("  nenhum xlsx encontrado"); return None
    log("  recurso:", rec.get("name"), "|", rec.get("last_modified"))
    return _baixar(rec["url"], ENTRADA / ("capag-municipios-%s.xlsx" % HOJE))

# ------------------------------------------------------------------ CAUC (csv, URL fixa)
CAUC_URL = "https://www.tesourotransparente.gov.br/ckan/dataset/72b5f371-0c35-4613-8076-c99c821a6410/resource/07af297a-5e59-494a-a88a-55ddfd2f4b01/download/relatorio-situacao-de-varios-entes---municipios---uf-todas---abrangencia-1.csv"
def cauc():
    log("CAUC: baixando o relatório dos municípios")
    p = ckan_pacote("cauc")
    url = CAUC_URL
    if p:
        rec = _recurso_mais_novo(p["resources"], r"munic[ií]pios.*todas", ("csv",))
        if rec: url = rec["url"]
    return _baixar(url, ENTRADA / ("cauc-municipios-%s.csv" % HOJE))

# ------------------------------------------------------------------ SADIPEM (csv do CKAN ou API)
SADIPEM_API = "https://apidatalake.tesouro.gov.br/ords/sadipem/tt/pvl"
def sadipem():
    log("SADIPEM: procurando CSV no CKAN (dataset pvl-dados-basicos)")
    p = ckan_pacote("pvl-dados-basicos")
    if p:
        rec = _recurso_mais_novo(p["resources"], r".", ("csv",))
        if rec:
            log("  recurso:", rec.get("name"), "|", rec.get("last_modified"))
            return _baixar(rec["url"], ENTRADA / ("sadipem-%s.csv" % HOJE))
    log("  sem CSV no CKAN — tentando a API paginada", SADIPEM_API)
    itens, offset = [], 0
    while True:
        r = _get(SADIPEM_API, params={"limit": 5000, "offset": offset}, timeout=300)
        if not r: break
        j = r.json(); lote = j.get("items", [])
        itens.extend(lote); offset += len(lote)
        log("  ", len(itens), "registros")
        if not j.get("hasMore") or not lote: break
        time.sleep(0.5)
    if not itens: return None
    # grava como CSV com o cabeçalho da própria API (extrair.sadipem aceita sinônimos)
    import csv
    dest = ENTRADA / ("sadipem-api-%s.csv" % HOJE)
    with open(dest, "w", encoding="latin-1", errors="replace", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(itens[0].keys()), delimiter=";")
        w.writeheader(); w.writerows(itens)
    log("  salvo", dest.name, "| colunas:", list(itens[0].keys()))
    return dest

# ------------------------------------------------------------------ CDP (6 csv)
CDP_ARQS = {"01": r"01-dados-basicos", "02": r"02-dividas\.csv", "05": r"05-dividas-execucao-financeira",
            "06": r"06-garantias\.csv", "10": r"10-pvls-nao-vinculados", "13": r"13-criterios-homologacao"}
def cdp():
    log("CDP: procurando o conjunto de dados no CKAN")
    pacotes = ckan_busca("Cadastro da Dívida Pública CDP")
    alvo = None
    for p in pacotes:
        nomes = " ".join((r.get("name") or "") + " " + (r.get("url") or "") for r in p.get("resources", []))
        if re.search(r"02-dividas", nomes): alvo = p; break
    if not alvo:
        log("  conjunto com os arquivos '-02-dividas.csv' não encontrado — use a carga manual em entrada/"); return {}
    out = {}
    for k, pad in CDP_ARQS.items():
        rec = _recurso_mais_novo(alvo["resources"], pad, ("csv",))
        if not rec: log("  arquivo", k, "ausente no CKAN"); continue
        dest = _baixar(rec["url"], ENTRADA / ("%s-%s.csv" % (HOJE, Path(rec["url"]).stem.split("-", 1)[-1] if "-" in Path(rec["url"]).stem else k)))
        if dest: out[k] = dest
    return out
