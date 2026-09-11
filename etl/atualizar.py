# -*- coding: utf-8 -*-
"""
Orquestrador do ETL.
  python etl/atualizar.py            -> usa só os arquivos de entrada/ (carga manual)
  python etl/atualizar.py --baixar   -> tenta baixar do Tesouro antes; se falhar, usa entrada/
Regra de ouro: uma camada que falha NÃO derruba o painel — fica a versão anterior, com aviso em meta.json.
"""
import argparse, json, re, shutil, sys, traceback
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import ENTRADA, DADOS, log, gravar_gz, ler_gz, mais_recente
import extrair

def data_do_nome(p):
    m = re.search(r"(\d{4})(\d{2})(\d{2})", p.name) or re.search(r"(\d{4})-(\d{2})-(\d{2})", p.name)
    if m: return "%s/%s/%s" % (m.group(3), m.group(2), m.group(1))
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--baixar", action="store_true"); a = ap.parse_args()
    ENTRADA.mkdir(exist_ok=True); DADOS.mkdir(parents=True, exist_ok=True)
    anterior = ler_gz(DADOS / "base.json.gz") if (DADOS / "base.json.gz").exists() else None
    meta = dict((anterior or {}).get("meta", {})); meta["avisos"] = []; meta["atualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    base = {"meta": meta, "mun": (anterior or {}).get("mun", []), "sit": (anterior or {}).get("sit", {}),
            "sad": (anterior or {}).get("sad", {}), "cdp": (anterior or {}).get("cdp", {}), "ppp": (anterior or {}).get("ppp", {}),
            "dic": dict((anterior or {}).get("dic", {}))}
    if a.baixar:
        import fontes

    def aviso(s): log("AVISO:", s); meta["avisos"].append(s)

    # ---------------- CAPAG
    try:
        arq = (fontes.capag() if a.baixar else None) or mais_recente(ENTRADA, r"capag.*\.xlsx$")
        if arq:
            base["mun"] = extrair.capag(arq); meta["capag"] = "%s (arquivo %s)" % (data_do_nome(arq), arq.name)
        elif not base["mun"]: raise FileNotFoundError("nenhuma planilha capag-*.xlsx em entrada/")
    except Exception as e:
        aviso("CAPAG mantida da versão anterior: %s" % e); traceback.print_exc()
    if not base["mun"]:
        log("Sem CAPAG não há painel. Coloque a planilha em entrada/ e rode de novo."); sys.exit(1)
    BY = {m["c"]: m for m in base["mun"]}

    # ---------------- CAUC
    try:
        arq = (fontes.cauc() if a.baixar else None) or mais_recente(ENTRADA, r"(cauc|relatorio-situacao).*\.csv$")
        if arq:
            r = extrair.cauc(arq)
            datas = {}
            for k, v in r["sit"].items():
                v["d"] = [datas.setdefault(x, len(datas)) for x in v["d"]]
            base["sit"] = r["sit"]; base["dic"]["cauc_val"] = list(datas)
            meta["sit"] = r["meta"]; meta["cauc"] = r["codes"]
            for c, p in r["pop"].items():
                if c in BY: BY[c]["pop"] = p
    except Exception as e:
        aviso("CAUC mantido da versão anterior: %s" % e); traceback.print_exc()

    # ---------------- SADIPEM
    try:
        arq = (fontes.sadipem() if a.baixar else None) or mais_recente(ENTRADA, r"sadipem.*\.csv$")
        if arq:
            r = extrair.sadipem(arq)
            base["sad"] = r["sad"]; base["dic"].update(r["dic"]); meta["sadipem"] = r["ref"] or data_do_nome(arq)
    except Exception as e:
        aviso("SADIPEM mantido da versão anterior: %s" % e); traceback.print_exc()

    # ---------------- CDP
    try:
        arqs = fontes.cdp() if a.baixar else {}
        if not arqs:
            for k, pad in {"01": r"01-dados-basicos", "02": r"02-dividas\.csv", "05": r"05-dividas-execucao-financeira",
                           "06": r"06-garantias\.csv", "10": r"10-pvls-nao-vinculados", "13": r"13-criterios-homologacao"}.items():
                p = mais_recente(ENTRADA, pad)
                if p: arqs[k] = p
        if arqs:
            r = extrair.cdp(arqs, base["mun"])
            base["cdp"] = r["cdp"]; base["dic"].update(r["dic"])
            meta["cdp"] = data_do_nome(sorted(arqs.values(), key=lambda p: p.stat().st_mtime)[-1])
    except Exception as e:
        aviso("CDP mantido da versão anterior: %s" % e); traceback.print_exc()

    # ---------------- PPP (cache da API do Siconfi tem prioridade; senão, planilha em entrada/)
    try:
        api = DADOS / "ppp.json"
        arq = mais_recente(ENTRADA, r"ppp.*\.xlsx$")
        if api.exists() and (not arq or api.stat().st_mtime > arq.stat().st_mtime):
            j = json.load(open(api, encoding="utf-8")); base["ppp"] = j["ppp"]; meta["ppp"] = j["ref"]
        elif arq:
            base["ppp"] = extrair.ppp_planilha(arq); meta["ppp"] = "RREO Anexo 13 (planilha %s)" % arq.name
    except Exception as e:
        aviso("PPP mantida da versão anterior: %s" % e); traceback.print_exc()

    # ---------------- grava
    tam = gravar_gz(DADOS / "base.json.gz", base)
    resumo = {"atualizado": meta["atualizado"], "capag": meta.get("capag"), "cauc": (meta.get("sit") or [""])[0],
              "sadipem": meta.get("sadipem"), "cdp": meta.get("cdp"), "ppp": meta.get("ppp"),
              "municipios": len(base["mun"]), "contratos_cdp": sum(len(e.get("div", [])) for e in base["cdp"].values()),
              "pedidos_sadipem": sum(len(v) for v in base["sad"].values()), "avisos": meta["avisos"], "tamanho_mb": round(tam / 1e6, 2)}
    json.dump(resumo, open(DADOS / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("Base gravada:", round(tam / 1e6, 2), "MB |", json.dumps(resumo, ensure_ascii=False))
    if meta["avisos"]: log("Concluído COM AVISOS — veja meta.json")

if __name__ == "__main__":
    main()
