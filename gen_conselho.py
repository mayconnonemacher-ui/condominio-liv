# Gera a página pública (somente leitura) para o conselho a partir do banco do painel interno + aba Demandas da planilha.
import json, glob, html, datetime, os
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("LIV_DBDUMP", "/home/claude/dbdump")

# Fonte de dados: (a) fornecedores.json compacto ao lado do script (gerado pelo painel interno e entregue via Google Drive)
# ou (b) a pasta dbdump/fornecedores/*.json exportada diretamente do banco do painel (read_db).
_compact = os.path.join(HERE, "fornecedores.json")
if os.path.exists(_compact):
    rows = json.load(open(_compact, encoding="utf-8"))
else:
    rows = [json.load(open(f, encoding="utf-8")) | {"id": f.split("/")[-1][:-5]} for f in glob.glob(os.path.join(DB, "fornecedores", "*.json"))]
for _r in rows:
    _r.setdefault("status", "A contatar"); _r.setdefault("endereco", ""); _r.setdefault("dataVisita", ""); _r.setdefault("valorMensal", None); _r.setdefault("valorAvulso", None)
dem = json.load(open(os.path.join(HERE, "demandas.json"), encoding="utf-8"))  # aba Demandas da planilha, exportada

CATS = ["Administração/contabilidade", "Portaria / Zeladoria / Limpeza", "Portaria remota", "Controle de pragas / Caixa d'água",
        "Análise de água (poço)", "Piscineiro", "Jardinagem", "Extintores / incêndio", "Elevadores", "Seguro", "Gás (GLP)", "Manutenção predial", "Outros"]
MAP = {1: "Portaria / Zeladoria / Limpeza", 2: "Portaria / Zeladoria / Limpeza", 3: "Análise de água (poço)", 4: "Controle de pragas / Caixa d'água",
       5: "Controle de pragas / Caixa d'água", 6: "Piscineiro", 7: "Portaria remota", 8: "Administração/contabilidade", 9: "Jardinagem",
       10: "Elevadores", 11: "Extintores / incêndio", 12: "Manutenção predial", 13: "Seguro", 14: "Outros"}
STATUS = ["A contatar", "Contatado", "Visita agendada", "Visita realizada", "Orçamento recebido", "Contratado", "Descartado"]
PUB = {"A contatar": "Contato pendente", "Contatado": "Em contato", "Visita agendada": "Visita agendada", "Visita realizada": "Visita realizada",
       "Orçamento recebido": "Proposta recebida", "Contratado": "Contratado", "Descartado": "Descartado"}
e = html.escape
def brl(v): return "—" if v in (None, "", 0) else "R$ " + f"{float(v):,.0f}".replace(",", ".")
def brd(iso): return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"
sidx = lambda s: max(0, STATUS.index(s) if s in STATUS else 0)
today = datetime.date.today()
upd = today.strftime("%d/%m/%Y")

active = [r for r in rows if r.get("status") != "Descartado"]
contatados = [r for r in active if sidx(r["status"]) >= 1]
propostas = [r for r in active if sidx(r["status"]) >= 4]
contratados = [r for r in rows if r.get("status") == "Contratado"]
best = {}
for r in active:
    v = r.get("valorMensal")
    if v and (r["categoria"] not in best or v < best[r["categoria"]]["v"]): best[r["categoria"]] = {"v": v, "e": r["empresa"]}
estimado = sum(b["v"] for b in best.values())
tot_contr = sum(r.get("valorMensal") or 0 for r in contratados)
visitas = sorted([r for r in active if r.get("dataVisita") and r["dataVisita"] >= today.isoformat()], key=lambda r: r["dataVisita"])

def kpi(l, v, s, hi=False):
    return f'<div class="kpi{" hi" if hi else ""}"><div class="lbl">{l}</div><div class="val">{v}</div><div class="sub">{s}</div></div>'

kpis = kpi("Serviços em cotação", len([c for c in CATS if any(r["categoria"] == c for r in rows)]), f"{len(dem)} demandas mapeadas") + \
       kpi("Fornecedores contatados", f"{len(contatados)}<small>/{len(active)}</small>", "meta: 3 propostas por serviço") + \
       kpi("Propostas recebidas", len(propostas), f"em {len({r['categoria'] for r in propostas})} serviços") + \
       kpi("Custo mensal estimado", brl(estimado) if estimado else "—", "menor proposta por serviço" if estimado else "aguardando propostas", True) + \
       kpi("Contratado até agora", brl(tot_contr) if tot_contr else str(len(contratados)), f"{len(contratados)} contrato(s) firmado(s)")

# resumo de custos
cost_rows = ""
for c in CATS:
    rs = [r for r in active if r["categoria"] == c]
    if not rs: continue
    vals = [r["valorMensal"] for r in rs if r.get("valorMensal")]
    ctr = [r for r in rs if r["status"] == "Contratado"]
    got = len([r for r in rs if sidx(r["status"]) >= 4])
    prog = "".join(f'<i class="{"on" if i < got else ""}"></i>' for i in range(3))
    cost_rows += f'<tr><td>{e(c)}</td><td><span class="prog">{prog}</span> {got}/3</td><td class="n">{brl(min(vals)) if vals else "—"}</td><td class="n c-md">{brl(sum(vals)/len(vals)) if vals else "—"}</td><td class="n c-md">{brl(max(vals)) if vals else "—"}</td><td class="c-md">{e(ctr[0]["empresa"]) + " · " + brl(ctr[0].get("valorMensal")) if ctr else "<span class=muted>em cotação</span>"}</td></tr>'
cost_rows += f'<tr class="tot"><td>Total mensal estimado</td><td></td><td class="n">{brl(estimado) if estimado else "—"}</td><td class="c-md"></td><td class="c-md"></td><td class="c-md">{brl(estimado*12).replace(" ", "&nbsp;") + "/ano" if estimado else ""}</td></tr>'

# seções por serviço
secs = ""
for c in CATS:
    rs = sorted([r for r in rows if r["categoria"] == c], key=lambda r: (-sidx(r["status"]) if r["status"] != "Descartado" else 9, r["empresa"]))
    ds = [d for d in dem if MAP.get(d[0]) == c]
    if not rs and not ds: continue
    dhtml = "".join(f'<div class="dem"><div class="dt">{e(d[1])}</div><div class="dd">{e(d[2])}</div><div class="dm"><span><b>Periodicidade</b> {e(d[3])}</span><span><b>Prioridade</b> {e(d[6])}</span></div><div class="dl"><b>Base legal / normativa</b> {e(d[4])}</div></div>' for d in ds)
    trs = "".join(f'<tr class="{"done" if r["status"]=="Contratado" else "out" if r["status"]=="Descartado" else ""}"><td>{e(r["empresa"])}<small>{e((r.get("endereco") or "").split("(")[0].strip())}</small></td><td><span class="pill st{sidx(r["status"])}">{PUB[r["status"]]}</span></td><td>{brd(r.get("dataVisita"))}</td><td class="n">{brl(r.get("valorMensal"))}</td><td class="n c-md">{brl(r.get("valorAvulso"))}</td></tr>' for r in rs) or '<tr><td colspan="5" class="muted">Nenhum fornecedor mapeado ainda.</td></tr>'
    got = len([r for r in rs if r["status"] != "Descartado" and sidx(r["status"]) >= 4])
    secs += f'''<section class="svc" id="{e(c)}"><div class="svc-h"><h2>{e(c)}</h2><span class="tag">{got}/3 propostas · {len([r for r in rs if r["status"]!="Descartado"])} fornecedores</span></div>
    <div class="svc-body"><div class="dems">{dhtml or '<div class="muted">Sem demanda detalhada — serviço complementar.</div>'}</div>
    <div class="tw"><table><thead><tr><th>Fornecedor</th><th>Situação</th><th>Visita</th><th class="n">Mensal</th><th class="n c-md">Avulso / implantação</th></tr></thead><tbody>{trs}</tbody></table></div></div></section>'''

vis = "".join(f'<li><span class="d">{brd(r["dataVisita"])}</span><span class="w">{e(r["empresa"])}</span><small>{e(r["categoria"])}</small></li>' for r in visitas[:12]) or '<li class="muted">Nenhuma visita técnica agendada no momento.</li>'

# ---------------------------------------------------------------------------
# ORÇAMENTO, FLUXO DE CAIXA E CAPITAL DE GIRO (a partir de premissas.json + propostas do painel)
# ---------------------------------------------------------------------------
_pp = os.path.join(HERE, "premissas.json")
orc_section = ""
if os.path.exists(_pp):
    PR = json.load(open(_pp, encoding="utf-8"))
    import calendar
    def _add_months(d, n):
        y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
        return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
    def _low(s): return (s or "").lower()
    unid = int(PR["unidades"]); isentos = int(PR.get("unidades_isentas", 0)); pag = max(unid - isentos, 0)
    taxa = PR.get("taxa_adotada") or PR["taxa_construtora"]; fr = float(PR["fundo_reserva"])
    ini = datetime.date.fromisoformat(PR["inicio_servicos"])
    venc, dpag, dcon = int(PR["dia_vencimento_boleto"]), int(PR["dia_pagto_prestadores"]), int(PR["dia_pagto_concessionarias"])
    saldo0 = float(PR.get("saldo_inicial", 0)); aporte_u = float(PR.get("aporte_por_unidade", 0))
    portaria = PR.get("modelo_portaria", "Remota"); elev = int(PR.get("elevadores", 1)); meses_res = float(PR.get("reserva_seguranca_meses", 1))
    # ---- valor usado por linha
    linhas = []
    by_id = {}
    for ln in PR["linhas"]:
        ativo = (ln.get("portaria") in (None, portaria))
        origem, valor, impl, quem = "estimativa", None, 0.0, ""
        cands = []
        if ln.get("categoria") and ln.get("campo"):
            for r in active:
                if r["categoria"] != ln["categoria"]: continue
                nm = _low(r["empresa"])
                if any(k.lower() in nm for k in ln.get("empresa_nao_contem", [])): continue
                if ln.get("empresa_contem") and not any(k.lower() in nm for k in ln["empresa_contem"]): continue
                if r.get(ln["campo"]) in (None, "", 0): continue
                cands.append(r)
            ctr = [r for r in cands if r["status"] == "Contratado"]
            props = [r for r in cands if sidx(r["status"]) >= 4]
            pick = ctr[0] if ctr else (min(props, key=lambda r: float(r[ln["campo"]])) if props else None)
            if pick:
                valor = float(pick[ln["campo"]]); origem = "contratado" if ctr else "proposta"; quem = pick["empresa"]
                if ln.get("implantacao_campo") and pick.get(ln["implantacao_campo"]) not in (None, "", 0):
                    impl = float(pick[ln["implantacao_campo"]])
                elif ln.get("implantacao_est"):
                    impl = float(ln["implantacao_est"])
        if valor is None and ln.get("igual_linha"):
            src = by_id.get(ln["igual_linha"]); valor = src["valor"] if src else 0.0; origem = src["origem"] if src else "estimativa"; quem = src["quem"] if src else ""
        if valor is None:
            valor = (float(ln.get("est_min", 0)) + float(ln.get("est_max", 0))) / 2
            if ln.get("por_elevador"): valor *= elev
            if ln.get("implantacao_est"): impl = float(ln["implantacao_est"])
        tipo = ln.get("tipo", "Prestador"); freq = int(ln.get("freq", 1)); first = int(ln.get("primeira", 1))
        if tipo == "Implantacao": impl, mensal_eq, sched = valor, 0.0, [0.0] * 12
        else:
            mensal_eq = valor / freq
            sched = [valor if (m >= first and (m - first) % freq == 0) else 0.0 for m in range(1, 13)]
        if not ativo: mensal_eq, sched, impl = 0.0, [0.0] * 12, 0.0
        item = dict(ln, valor=valor, origem=origem, quem=quem, impl=impl, mensal_eq=mensal_eq, sched=sched, ativo=ativo, tipo=tipo, freq=freq)
        linhas.append(item); by_id[ln["id"]] = item
    desp_mensal = sum(l["mensal_eq"] for l in linhas)
    impl_total = sum(l["impl"] for l in linhas if l["ativo"])
    prest_m = [sum(l["sched"][m] for l in linhas if l["tipo"] == "Prestador") for m in range(12)]
    conc_m = [sum(l["sched"][m] for l in linhas if l["tipo"] == "Concessionaria") for m in range(12)]
    arrec_nec = desp_mensal / (1 - fr) if fr < 1 else 0
    taxa_nec = arrec_nec / pag if pag else 0
    taxa_nec_inad = taxa_nec / PR["cenarios"]["base"]["em_dia"]
    # ---- fluxo mensal e diário por cenário
    def cenario(cn):
        c = PR["cenarios"][cn]; emd, a30, a60, defas, fat = c["em_dia"], c["atraso30"], c["atraso60"], int(c["defasagem_boleto"]), float(c["fator_despesa"])
        bruta = taxa * pag
        meses = []
        saldo, fracum = saldo0, 0.0
        for m in range(1, 13):
            b = bruta if m > defas else 0.0
            rec = b * emd + (bruta * a30 if m - 1 > defas else 0) + (bruta * a60 if m - 2 > defas else 0)
            ent = rec + (aporte_u * unid if m == 1 else 0)
            sai = (impl_total * fat if m == 1 else 0) + (prest_m[m - 2] * fat if m >= 2 else 0) + (conc_m[m - 2] * fat if m >= 2 else 0)
            saldo += ent - sai; fracum += fr * rec
            meses.append(dict(m=m, data=_add_months(ini, m - 1), ent=ent, sai=sai, saldo=saldo, fr=fracum, livre=saldo - fracum))
        # diário 92 dias
        dias = []; s = saldo0; fa = 0.0; worst = (None, 1e18)
        for i in range(92):
            d = ini + datetime.timedelta(days=i)
            mn = (d.year - ini.year) * 12 + d.month - ini.month + 1
            ent = (aporte_u * unid if i == 0 else 0)
            rec = 0.0
            if d.day == venc:
                rec = (bruta * emd if mn > defas else 0) + (bruta * a30 if mn - 1 > defas else 0) + (bruta * a60 if mn - 2 > defas else 0)
            sai = (impl_total * fat if i == 0 else 0)
            if mn >= 2 and d.day == dpag: sai += prest_m[mn - 2] * fat
            if mn >= 2 and d.day == dcon: sai += conc_m[mn - 2] * fat
            s += ent + rec - sai; fa += fr * rec
            livre = s - fa
            if livre < worst[1]: worst = (d, livre)
            dias.append((d, livre))
        return dict(meses=meses, pior_dia=worst[0], pior=worst[1], fat=fat)
    CEN = {k: cenario(k) for k in ("base", "pessimista")}
    def capital(cn):
        c = CEN[cn]; sem_aporte = c["pior"] - aporte_u * unid
        reserva = meses_res * desp_mensal * c["fat"]
        minimo = max(0.0, -sem_aporte); recomendado = minimo + reserva
        return dict(impl=impl_total * c["fat"], pior=sem_aporte, dia=c["pior_dia"], reserva=reserva, minimo=minimo, recomendado=recomendado, aporte=recomendado / unid if unid else 0)
    CAP = {k: capital(k) for k in CEN}
    # ---- render
    def pill_orig(o, quem):
        cls = {"contratado": "st5", "proposta": "st4", "estimativa": "st1"}[o]
        lab = {"contratado": "Contratado", "proposta": "Proposta", "estimativa": "Estimativa"}[o]
        return f'<span class="pill {cls}">{lab}</span>' + (f'<small>{e(quem)}</small>' if quem else "")
    def per(freq, tipo):
        if tipo == "Implantacao": return "única"
        return {1: "mensal", 3: "trimestral", 6: "semestral", 12: "anual"}.get(freq, f"a cada {freq} meses")
    otr = ""
    for l in linhas:
        if not l["ativo"]: continue
        otr += f'<tr><td>{e(l["nome"])}</td><td>{pill_orig(l["origem"], l["quem"])}</td><td class="n c-md">{brl(l["valor"])}<small>{per(l["freq"], l["tipo"])}</small></td><td class="n">{brl(l["mensal_eq"])}</td><td class="n c-md">{brl(l["mensal_eq"]*12)}</td><td class="n c-md">{brl(l["impl"])}</td></tr>'
    otr += f'<tr class="tot"><td>Total</td><td></td><td class="c-md"></td><td class="n">{brl(desp_mensal)}</td><td class="n c-md">{brl(desp_mensal*12)}</td><td class="n c-md">{brl(impl_total)}</td></tr>'
    n_est = len([l for l in linhas if l["ativo"] and l["origem"] == "estimativa"]); n_prop = len([l for l in linhas if l["ativo"] and l["origem"] != "estimativa"])
    # gráfico SVG do caixa livre mensal (base × pessimista)
    W, H, pl, pr_, pt, pb = 640, 220, 56, 12, 14, 30
    vals = [x["livre"] for x in CEN["base"]["meses"]] + [x["livre"] for x in CEN["pessimista"]["meses"]] + [0]
    vmin, vmax = min(vals), max(vals); span = (vmax - vmin) or 1
    def X(i): return pl + i * (W - pl - pr_) / 11
    def Y(v): return pt + (vmax - v) * (H - pt - pb) / span
    def path(cn): return "M" + " L".join(f"{X(i):.1f},{Y(x['livre']):.1f}" for i, x in enumerate(CEN[cn]["meses"]))
    MESN = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    ticks = "".join(f'<text x="{X(i):.1f}" y="{H-8}" text-anchor="middle" class="ax">{MESN[x["data"].month-1]}/{str(x["data"].year)[2:]}</text>' for i, x in enumerate(CEN["base"]["meses"]))
    grid = ""
    for k in range(5):
        v = vmin + span * k / 4
        grid += f'<line x1="{pl}" x2="{W-pr_}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="gl"/><text x="{pl-6}" y="{Y(v)+4:.1f}" text-anchor="end" class="ax">{("-" if v<0 else "")}{abs(v)/1000:.0f}k</text>'
    zero = f'<line x1="{pl}" x2="{W-pr_}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="zl"/>' if vmin < 0 < vmax else ""
    svg = f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="Caixa livre projetado ao fim de cada mês, cenários base e pessimista" style="width:100%;height:auto;max-width:100%"><style>.gl{{stroke:var(--line);stroke-width:1}}.zl{{stroke:var(--ink-3);stroke-width:1.2;stroke-dasharray:4 3}}.ax{{font:10px "IBM Plex Mono",monospace;fill:var(--ink-3)}}.lb{{stroke:var(--accent);stroke-width:2.5;fill:none}}.lp{{stroke:var(--warn);stroke-width:2.5;fill:none;stroke-dasharray:6 4}}</style>{grid}{zero}{ticks}<path d="{path('base')}" class="lb"/><path d="{path('pessimista')}" class="lp"/></svg>'''
    cb, cp = CAP["base"], CAP["pessimista"]
    folga = PR["taxa_construtora"] - taxa_nec
    cen_b, cen_p = PR["cenarios"]["base"], PR["cenarios"]["pessimista"]
    orc_kpis = kpi("Despesa operacional mensal", brl(desp_mensal), f"{brl(desp_mensal*12)} por ano · {n_prop} com proposta, {n_est} estimados") + \
        kpi("Taxa necessária por unidade", brl(taxa_nec), f"{brl(taxa_nec_inad)} com inadimplência de {100-cen_b['em_dia']*100:.0f}%") + \
        kpi("Estimativa da construtora", brl(PR["taxa_construtora"]), (f"folga de {brl(folga)}/unidade" if folga >= 0 else f"faltam {brl(-folga)}/unidade"), True) + \
        kpi("Implantação única", brl(impl_total), "desembolsos de uma vez, no início") + \
        kpi("Caixa mínimo inicial", brl(cp["recomendado"]), f"cenário pessimista · {brl(cb['recomendado'])} no base") + \
        kpi("Cota de implantação por unidade", brl(cp["aporte"]), f"cota única, pessimista · {brl(cb['aporte'])} no base")
    orc_section = f'''<section class="panel" id="orcamento"><h2 style="margin-bottom:6px">Orçamento anual e caixa mínimo inicial</h2>
<p class="muted" style="font-size:13px;margin:0 0 12px;max-width:80ch">Projeção que se atualiza com as propostas do painel: para cada serviço vale o valor contratado, senão a menor proposta recebida, senão uma estimativa de mercado (marcada como tal). Rateio igual entre {unid} unidades; início dos serviços em {ini.strftime("%d/%m/%Y")}; fundo de reserva de {fr*100:.0f}%; portaria {portaria.lower()}.</p>
<div class="kpis">{orc_kpis}</div>
<div class="two">
<div><h2 style="font-size:14px;margin:0 0 6px">Caixa livre ao fim de cada mês</h2>
<p class="muted" style="font-size:12px;margin:0 0 8px">Linha cheia: cenário base ({cen_b['em_dia']*100:.0f}% dos boletos em dia, 1º boleto no mês {1+cen_b['defasagem_boleto']}). Tracejada: pessimista ({cen_p['em_dia']*100:.0f}% em dia, 1º boleto no mês {1+cen_p['defasagem_boleto']}, despesas +{(cen_p['fator_despesa']-1)*100:.0f}%). Sem aporte inicial{"" if aporte_u == 0 else f" além de {brl(aporte_u)}/unidade"}; fundo de reserva já descontado.</p>
{svg}</div>
<div><div class="tw"><table><thead><tr><th>Capital de giro</th><th class="n">Base</th><th class="n">Pessimista</th></tr></thead><tbody>
<tr><td>Implantação única</td><td class="n">{brl(cb['impl'])}</td><td class="n">{brl(cp['impl'])}</td></tr>
<tr><td>Pior dia do caixa livre nos 90 primeiros dias<small>{cb['dia'].strftime("%d/%m/%Y")} · {cp['dia'].strftime("%d/%m/%Y")}</small></td><td class="n">{brl(cb['pior'])}</td><td class="n">{brl(cp['pior'])}</td></tr>
<tr><td>Mínimo para o caixa não ficar negativo</td><td class="n">{brl(cb['minimo'])}</td><td class="n">{brl(cp['minimo'])}</td></tr>
<tr><td>Reserva de segurança ({meses_res:g} mês de despesa)</td><td class="n">{brl(cb['reserva'])}</td><td class="n">{brl(cp['reserva'])}</td></tr>
<tr class="tot"><td>Caixa mínimo inicial recomendado</td><td class="n">{brl(cb['recomendado'])}</td><td class="n">{brl(cp['recomendado'])}</td></tr>
<tr><td>Cota única de implantação por unidade</td><td class="n">{brl(cb['aporte'])}</td><td class="n">{brl(cp['aporte'])}</td></tr>
</tbody></table></div></div>
</div>
<h2 style="font-size:14px;margin:16px 0 6px">Orçamento por item</h2>
<div class="tw"><table><thead><tr><th>Item</th><th>Origem do valor</th><th class="n c-md">Valor</th><th class="n">Por mês</th><th class="n c-md">Ano</th><th class="n c-md">Implantação</th></tr></thead><tbody>{otr}</tbody></table></div>
<details style="margin-top:12px"><summary class="muted" style="cursor:pointer;font-size:13px">Premissas e método</summary>
<p class="muted" style="font-size:12px;max-width:90ch">Boletos vencem no dia {venc}; prestadores são pagos no dia {dpag} do mês seguinte à competência e concessionárias no dia {dcon}. Atrasos de 30 e 60 dias são recebidos nos vencimentos seguintes. O fundo de reserva ({fr*100:.0f}% do recebido) fica segregado e não conta como caixa livre. Taxa necessária = despesa mensal ÷ (1 − fundo de reserva) ÷ unidades pagantes. Caixa mínimo = o que falta para o caixa livre não ficar negativo no pior dia dos 90 primeiros dias (já incluindo a implantação) + reserva de segurança. Estimativas de mercado (Cascavel, set/2026) não são propostas e são substituídas automaticamente quando uma proposta é lançada no painel. Itens sem categoria no painel (energia, tarifas, material) permanecem estimados até a primeira fatura.</p></details>
</section>'''

page = f'''<title>Cotações LIV — Conselho</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#F2F5F3;--surface:#FFF;--surface-2:#E9EEEB;--line:#D5DDD9;--line-strong:#B9C5BF;--ink:#16221F;--ink-2:#4B5B56;--ink-3:#7C8B86;--accent:#0F6E63;--accent-ink:#FFF;--accent-soft:#D7EBE7;--good:#2E7D32;--good-soft:#DFF0E0;--warn:#A8701A;--warn-soft:#F6E8CC;--muted-soft:#ECEFEE;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0F1614;--surface:#172020;--surface-2:#1F2A29;--line:#2C3937;--line-strong:#3C4B48;--ink:#E7EDEA;--ink-2:#AEBCB7;--ink-3:#7F8E89;--accent:#4FB8A9;--accent-ink:#0B1513;--accent-soft:#1B3B37;--good:#7BC67E;--good-soft:#1C3220;--warn:#E0B25B;--warn-soft:#3A2E14;--muted-soft:#232D2B;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#0F1614;--surface:#172020;--surface-2:#1F2A29;--line:#2C3937;--line-strong:#3C4B48;--ink:#E7EDEA;--ink-2:#AEBCB7;--ink-3:#7F8E89;--accent:#4FB8A9;--accent-ink:#0B1513;--accent-soft:#1B3B37;--good:#7BC67E;--good-soft:#1C3220;--warn:#E0B25B;--warn-soft:#3A2E14;--muted-soft:#232D2B;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "IBM Plex Sans",system-ui,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 24px 56px}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:20px}}
.eyebrow{{font:500 11px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:6px}}
h1{{font:700 26px/1.15 "Sora",sans-serif;margin:0;letter-spacing:-.01em}} h2{{font:600 16px/1.2 "Sora",sans-serif;margin:0}}
.upd{{font:500 12px "IBM Plex Mono",monospace;color:var(--ink-2);padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface)}}
.intro{{color:var(--ink-2);max-width:70ch;margin:0 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:22px}}
.kpi{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}.kpi .lbl{{font-size:12px;color:var(--ink-2)}}.kpi .val{{font:600 26px/1.1 "Sora",sans-serif;margin-top:4px;font-variant-numeric:tabular-nums}}.kpi .val small{{font-size:14px;color:var(--ink-3)}}.kpi .sub{{font:400 11px "IBM Plex Mono",monospace;color:var(--ink-3);margin-top:4px}}
.kpi.hi{{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}}.kpi.hi .lbl,.kpi.hi .sub{{color:color-mix(in srgb,var(--accent-ink) 78%,transparent)}}
.panel{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:18px}}
.two{{display:grid;grid-template-columns:1.9fr 1fr;gap:16px}}.two td,.two th{{white-space:nowrap;padding-left:7px;padding-right:7px}}.two td:first-child{{white-space:normal}}@media(max-width:820px){{.two{{grid-template-columns:1fr}}}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}th{{text-align:left;font:500 11px "IBM Plex Mono",monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}tr:last-child td{{border-bottom:0}}
td small{{display:block;color:var(--ink-3);font-size:12px}}.n{{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}th.n{{text-align:right}}
tr.tot td{{font-weight:600;background:var(--surface-2)}}tr.done td{{background:color-mix(in srgb,var(--good-soft) 55%,transparent)}}tr.out td{{opacity:.5}}
.muted{{color:var(--ink-3)}}td.n small{{display:block;font:400 10.5px "IBM Plex Mono",monospace;color:var(--ink-3)}}#orcamento .two{{grid-template-columns:1.2fr 1fr;align-items:start}}@media(max-width:820px){{#orcamento .two{{grid-template-columns:1fr}}}}#orcamento .pill+small{{display:block;color:var(--ink-3);font-size:11px;margin-top:2px}}
.prog i{{display:inline-block;width:14px;height:6px;border-radius:2px;background:var(--surface-2);margin-right:2px;vertical-align:middle}}.prog i.on{{background:var(--accent)}}
.pill{{display:inline-block;padding:2px 8px;border-radius:999px;font:500 11px "IBM Plex Mono",monospace;white-space:nowrap}}.st0{{background:var(--muted-soft);color:var(--ink-2)}}.st1{{background:var(--warn-soft);color:var(--warn)}}.st2,.st3,.st4{{background:var(--accent-soft);color:var(--accent)}}.st5{{background:var(--good-soft);color:var(--good)}}.st6{{background:var(--muted-soft);color:var(--ink-3)}}
ul.vis{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}}ul.vis li{{display:flex;align-items:center;gap:10px;flex-wrap:nowrap;padding:8px 10px;border:1px solid var(--line);border-radius:8px;overflow:hidden}}ul.vis .w{{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}ul.vis .d{{flex:none;font:500 12px "IBM Plex Mono",monospace;color:var(--accent)}}ul.vis small{{margin-left:auto;flex:none;color:var(--ink-3);font-size:11px;white-space:nowrap;max-width:45%;overflow:hidden;text-overflow:ellipsis}}
.toc{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px}}.toc a{{font-size:12px;color:var(--accent);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 10px;background:var(--surface)}}.toc a:hover{{border-color:var(--accent)}}
.svc{{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden}}.svc-h{{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--surface-2)}}
.tag{{font:500 11px "IBM Plex Mono",monospace;color:var(--ink-2)}}.svc-body{{display:grid;grid-template-columns:0.9fr 1.6fr;gap:0}}.svc td:first-child{{min-width:210px}}.svc td:nth-child(2){{white-space:nowrap}}@media(max-width:820px){{.svc-body{{grid-template-columns:1fr}}}}
.dems{{padding:14px 16px;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:14px}}@media(max-width:820px){{.dems{{border-right:0;border-bottom:1px solid var(--line)}}}}
.dem .dt{{font-weight:600}}.dem .dd{{color:var(--ink-2);font-size:13px;margin:2px 0 6px}}.dem .dm{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-2)}}.dem b{{font-weight:500;color:var(--ink-3);font-family:"IBM Plex Mono",monospace;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;margin-right:4px}}.dem .dl{{font-size:12px;color:var(--ink-2);margin-top:6px}}
.svc-body .tw{{padding:6px 8px}}
.panel,.two>*,.svc-body>*,.svc{{min-width:0}}
@media(max-width:600px){{.wrap{{padding:16px 12px 40px}}h1{{font-size:22px}}.kpis{{grid-template-columns:1fr 1fr;gap:8px}}.kpi{{padding:10px 12px}}.kpi .val{{font-size:22px}}.c-md{{display:none}}td,th{{padding:8px 6px;font-size:13px}}.dems,.svc-h{{padding:12px}}.svc-body .tw{{padding:4px 2px}}.intro{{font-size:13px}}ul.vis small{{max-width:40%}}.two{{gap:12px}}
.svc thead{{display:none}}.svc tbody tr{{display:grid;grid-template-columns:1fr auto;gap:4px 10px;align-items:center;padding:10px 8px;border-bottom:1px solid var(--line)}}.svc tbody tr:last-child{{border-bottom:0}}.svc td{{display:block;border:0;padding:0;font-size:13px}}.svc td.c-md{{display:none}}.prog{{display:none}}ul.vis li.muted{{display:block}}th{{white-space:normal}}td{{font-size:12.5px}}.svc td:first-child{{grid-column:1/-1;font-weight:500}}.svc td:nth-child(3){{grid-column:1;color:var(--ink-2)}}.svc td:nth-child(3):not(:empty)::before{{content:"Visita: ";color:var(--ink-3)}}.svc td:nth-child(4){{grid-column:2;grid-row:2;text-align:right}}.svc td:nth-child(4)::before{{content:"Mensal ";font-family:"IBM Plex Sans",sans-serif;color:var(--ink-3)}}.svc td:nth-child(2){{grid-column:1;grid-row:2}}.svc tr.done td:first-child::after{{content:" · contratado";color:var(--good);font-weight:400;font-size:12px}}}}
@media(max-width:600px){{#orcamento .pill+small{{display:none}}#orcamento th,#orcamento td{{padding:6px 4px;font-size:12px}}#orcamento .pill{{font-size:10px;padding:2px 6px}}#orcamento td.n small{{display:none}}}}
.intro,.dem .dd,.dem .dl,#orcamento p,#orcamento details p,.panel>p.muted,footer{{text-align:justify;hyphens:auto;-webkit-hyphens:auto}}.kpis{{align-items:stretch}}.kpi{{display:flex;flex-direction:column}}.kpi .sub{{margin-top:auto;padding-top:4px}}.dem .dm{{justify-content:flex-start}}
footer{{font-size:12px;color:var(--ink-3);margin-top:24px;max-width:75ch}}
</style>
<div class="wrap">
<header><div><div class="eyebrow">Condomínio Residencial LIV · Cascavel-PR · Conselho</div><h1>Cotações LIV — Conselho</h1></div><div class="upd">atualizado em {upd}</div></header>
<p class="intro">Acompanhamento das cotações para contratação dos serviços de conservação e manutenção do condomínio. Para cada serviço estão o escopo pretendido, a base legal, os fornecedores consultados e as propostas recebidas. A regra adotada é obter no mínimo três propostas por serviço antes de levar a decisão à assembleia. Mais abaixo, o orçamento anual projetado e o caixa mínimo necessário antes do início dos contratos, recalculados a cada atualização.</p>
<div class="kpis">{kpis}</div>
<div class="two">
<div class="panel"><h2 style="margin-bottom:10px">Resumo de custos por serviço</h2><div class="tw"><table><thead><tr><th>Serviço</th><th>Propostas</th><th class="n">Menor</th><th class="n c-md">Média</th><th class="n c-md">Maior</th><th class="c-md">Contratado</th></tr></thead><tbody>{cost_rows}</tbody></table></div><p class="muted" style="font-size:12px;margin:10px 0 0">Valores mensais em reais, conforme propostas recebidas. Serviços anuais (seguro, extintores, limpeza de reservatório) são lançados pelo valor mensal equivalente.</p></div>
<div class="panel"><h2 style="margin-bottom:10px">Próximas visitas técnicas</h2><ul class="vis">{vis}</ul></div>
</div>
{orc_section}
<div class="toc">{'<a href="#orcamento">Orçamento e caixa inicial</a>' if orc_section else ''}{"".join(f'<a href="#{e(c)}">{e(c)}</a>' for c in CATS if any(r["categoria"]==c for r in rows) or any(MAP.get(d[0])==c for d in dem))}</div>
{secs}
<footer>Página de leitura para o conselho, gerada a partir do painel interno de cotações do síndico. Contatos, anotações internas e avaliações dos fornecedores não são exibidos aqui. Referências legais citadas são indicativas e devem ser confirmadas junto à Vigilância Sanitária, CREA e Corpo de Bombeiros antes da contratação.</footer>
</div>'''
open(os.path.join(HERE, "cotacoes-liv-conselho.html"), "w", encoding="utf-8").write(page)
# versão completa (documento HTML) para hospedagem no GitHub Pages
full = "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"robots\" content=\"noindex\">" + page.replace("<title>", "<title>", 1) + "</head><body></body></html>"
# move o conteúdo visual para o body: tudo após </style> pertence ao body
head_part, body_part = page.split("</style>", 1)
full = "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"robots\" content=\"noindex\">" + head_part + "</style></head><body>" + body_part + "</body></html>"
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(full)
print("ok", len(page))
