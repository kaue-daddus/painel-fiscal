# -*- coding: utf-8 -*-
"""
Coleta as PPPs municipais direto da API do Siconfi (RREO Anexo 13 — despesas de PPP;
RREO Anexo 03 — RCL dos últimos 12 meses), nos dois tipos de demonstrativo (RREO e RREO Simplificado).

É lento por natureza (uma chamada por município e por anexo/tipo, ~1 chamada/segundo):
roda como job mensal separado e grava um cache em docs/dados/ppp_siconfi.json, retomável.
Uso:  python etl/ppp_siconfi.py --exercicio 2025 --periodo 6 [--max-min 300]
"""
import argparse, json, re, sys, time
from pathlib import Path
import requests
from comum import DADOS, log, ler_gz

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"
UA = {"User-Agent": "Mozilla/5.0 (painel-fiscal-daddus)"}
CACHE = DADOS / "ppp_siconfi.json"

def consulta(id_ente, exercicio, periodo, tipo, anexo):
    p = {"an_exercicio": exercicio, "nr_periodo": periodo, "co_tipo_demonstrativo": tipo, "no_anexo": anexo, "id_ente": id_ente}
    for t in range(3):
        try:
            r = requests.get(API, params=p, headers=UA, timeout=60)
            if r.status_code == 200: return r.json().get("items", [])
            if r.status_code == 429: time.sleep(10); continue
        except requests.RequestException: time.sleep(3)
    return None

def rcl_de(itens):
    for it in itens:
        if re.match(r"RECEITA CORRENTE L[ÍI]QUIDA", (it.get("conta") or "").strip(), re.I) and re.search(r"12 MESES|TOTAL", (it.get("coluna") or ""), re.I):
            try: return float(it["valor"])
            except (TypeError, ValueError): pass
    return None

def ppp_de(itens):
    """Devolve (valor, coluna_de_origem) da linha de despesas de PPP, priorizando o exercício corrente."""
    cand = [it for it in itens if re.search(r"^(TOTAL DAS DESPESAS|DESPESAS DE PPP)", (it.get("conta") or "").strip(), re.I)]
    ordem = [r"CORRENTE", r"ANTERIOR", r"EC \+ 1|EC\+1", r"EC \+ 2|EC\+2"]
    for pad in ordem:
        for it in cand:
            if re.search(pad, it.get("coluna") or "", re.I):
                try:
                    v = float(it["valor"])
                    if v > 0: return v, it["coluna"]
                except (TypeError, ValueError): pass
    return None, ""

def origem(col):
    if not col: return ""
    return "EC" if "CORRENTE" in col.upper() else "ANT" if "ANTERIOR" in col.upper() else "PROJ"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercicio", type=int, required=True); ap.add_argument("--periodo", type=int, default=6)
    ap.add_argument("--max-min", type=int, default=300, help="tempo máximo de execução (minutos)")
    a = ap.parse_args()
    base = ler_gz(DADOS / "base.json.gz")
    muns = [(m["c"], m["n"], m["uf"]) for m in base["mun"]]
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    chave = "%d-%d" % (a.exercicio, a.periodo)
    if cache.get("_ref") != chave: cache = {"_ref": chave}
    t0 = time.time(); feitos = 0
    for c, n, uf in muns:
        if c in cache: continue
        if (time.time() - t0) / 60 > a.max_min: log("limite de tempo — retomo na próxima execução"); break
        reg = {"rcl": None, "v": None, "col": "", "tipo": "", "a13": False}
        for tipo in ("RREO", "RREO Simplificado"):
            a03 = consulta(c, a.exercicio, a.periodo, tipo, "RREO-Anexo 03")
            if a03 is None: continue
            r = rcl_de(a03)
            if r: reg["rcl"] = r; reg["tipo"] = tipo
            a13 = consulta(c, a.exercicio, a.periodo, tipo, "RREO-Anexo 13")
            if a13:
                reg["a13"] = True
                v, col = ppp_de(a13)
                if v: reg["v"], reg["col"] = v, col
            if reg["rcl"] is not None: break
            time.sleep(0.3)
        cache[c] = reg; feitos += 1
        if feitos % 50 == 0:
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            log(feitos, "municípios nesta execução |", sum(1 for k in cache if k != "_ref"), "no cache")
        time.sleep(0.3)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    # converte o cache no formato do painel e grava docs/dados/ppp.json (atualizar.py incorpora)
    P = {}
    for c, r in cache.items():
        if c == "_ref": continue
        sit = 1 if r["v"] else 2 if r["a13"] else 3 if r["rcl"] else 0
        P[c] = [sit, "%d - bim %d" % (a.exercicio, a.periodo) if r["rcl"] else "", r["tipo"], r["rcl"], r["v"],
                origem(r["col"]) if r["v"] else "", 0, 0, 0]
    json.dump({"ref": "RREO Anexo 13, %d %dº bim. (Siconfi API)" % (a.exercicio, a.periodo), "ppp": P},
              open(DADOS / "ppp.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("PPP: cache com", len(P), "de", len(muns), "municípios |", sum(1 for v in P.values() if v[4]), "com despesa")

if __name__ == "__main__":
    main()
