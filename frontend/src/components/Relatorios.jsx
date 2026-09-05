import { useState } from 'react';
import axios from 'axios';
import './Relatorios.css';

const API_URL = 'http://192.168.1.26:8000';

const PERIODOS = [
  { id: '1', label: 'Últimas 24h' },
  { id: '15', label: 'Últimos 15 dias' },
  { id: '30', label: 'Últimos 30 dias' },
  { id: '90', label: 'Últimos 3 meses' },
  { id: '180', label: 'Últimos 6 meses' },
  { id: '365', label: 'Últimos 12 meses' },
];

const CATEGORIAS_DISPONIVEIS = [
  { chave: 'servidores', label: 'Servidores', cor: 'var(--rel-s1)' },
  { chave: 'access_points', label: 'Access Points', cor: 'var(--rel-s2)' },
  { chave: 'links', label: 'Links de Rede', cor: 'var(--rel-s3)' },
  { chave: 'vpns', label: 'VPNs', cor: 'var(--rel-s6)' },
  { chave: 'vlans', label: 'VLANs', cor: 'var(--rel-s4)' },
  { chave: 'backups', label: 'Backups', cor: 'var(--rel-s5)' },
  { chave: 'acessos', label: 'Acessos (Internet)', cor: 'var(--rel-marca)' },
];

const ICONES_CATEGORIA = {
  servidores: <><rect x="3" y="4" width="18" height="6" rx="1.6" /><rect x="3" y="14" width="18" height="6" rx="1.6" /><path d="M7 7h.01M7 17h.01" /></>,
  access_points: <><path d="M2.5 8.5a16 16 0 0 1 19 0" /><path d="M6 12.5a11 11 0 0 1 12 0" /><path d="M9.5 16.4a6 6 0 0 1 5 0" /><circle cx="12" cy="20" r="1.1" fill="currentColor" stroke="none" /></>,
  links: <><circle cx="18" cy="5" r="2.6" /><circle cx="6" cy="12" r="2.6" /><circle cx="18" cy="19" r="2.6" /><path d="M8.3 10.7l7.4-4.3M8.3 13.3l7.4 4.3" /></>,
  vpns: <><rect x="3" y="11" width="18" height="10" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>,
  vlans: <><circle cx="18" cy="5" r="2.6" /><circle cx="6" cy="12" r="2.6" /><circle cx="18" cy="19" r="2.6" /><path d="M8.3 10.7l7.4-4.3M8.3 13.3l7.4 4.3" /></>,
  backups: <><path d="M6.5 18.5a4 4 0 0 1 .4-8 5.6 5.6 0 0 1 10.6 1.4 3.6 3.6 0 0 1-.7 6.6" /><path d="M12 21v-8M9 15.5l3-3 3 3" /></>,
};

function corFaixa(media) {
  if (media >= 99) return 'var(--rel-verde)';
  if (media >= 90) return 'var(--rel-ambar)';
  return 'var(--rel-vermelho)';
}
function classeFaixa(media) {
  if (media >= 99) return 'bom';
  if (media >= 90) return 'mid';
  return 'ruim';
}
function formatarDataHora(iso) {
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}
function formatarDataCurta(iso) {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}
function formatarBytesRel(n) {
  n = n || 0;
  const unidades = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < unidades.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(1)} ${unidades[i]}`;
}

// Gera um path SVG (viewBox 460x140, area util x:10-450 y:20-120) a partir
// de uma serie de pontos {t,v}, com escala minima/maxima dinamica (nao fixa),
// pra funcionar bem tanto num periodo de 24h quanto de 12 meses.
function gerarLinhaSVG(serie, cor) {
  if (!serie || serie.length < 2) return { path: '', area: '', pontos: [] };
  const valores = serie.map((p) => p.v);
  const min = Math.min(...valores, 0);
  const max = Math.max(...valores, 100);
  const faixa = max - min || 1;
  const x0 = 10, x1 = 450, y0 = 20, y1 = 120;
  const passoX = (x1 - x0) / (serie.length - 1 || 1);
  const pontos = serie.map((p, i) => ({
    x: x0 + i * passoX,
    y: y1 - ((p.v - min) / faixa) * (y1 - y0),
    v: p.v,
  }));
  const path = pontos.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L${pontos[pontos.length - 1].x.toFixed(1)},${y1} L${pontos[0].x.toFixed(1)},${y1} Z`;
  return { path, area, pontos };
}

// Gera os segmentos de um donut (stroke-dasharray) a partir de valores { label, valor, cor }
function gerarDonut(itens, raio = 46) {
  const total = itens.reduce((s, i) => s + i.valor, 0) || 1;
  const circunferencia = 2 * Math.PI * raio;
  let acumulado = 0;
  return itens.map((item) => {
    const proporcao = item.valor / total;
    const comprimento = proporcao * circunferencia;
    const offset = -acumulado;
    acumulado += comprimento;
    return { ...item, comprimento, offset, circunferencia };
  });
}

function IconeSeta({ tipo }) {
  if (tipo === 'alta') return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M6 11l6-6 6 6" /></svg>;
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M6 13l6 6 6-6" /></svg>;
}

function Relatorios({ token, role }) {
  const [periodoSelecionado, setPeriodoSelecionado] = useState('15');
  const [categoriasSelecionadas, setCategoriasSelecionadas] = useState(CATEGORIAS_DISPONIVEIS.map((c) => c.chave));
  const [dados, setDados] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [abaVisivel, setAbaVisivel] = useState('geral');
  const [nomesRevelados, setNomesRevelados] = useState({});
  const podeRevelarIdentidade = role === 'admin' || role === 'super_admin';
  const revelarIdentidadeAcessos = (mac, ip) => {
    if (!podeRevelarIdentidade || nomesRevelados[mac] || !ip) return;
    axios.get(`${API_URL}/dashboard/acessos/identidade-vpn`, {
      params: { ip },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setNomesRevelados((prev) => ({ ...prev, [mac]: r.data.nome || 'Não encontrado' })))
      .catch(() => setNomesRevelados((prev) => ({ ...prev, [mac]: 'Erro ao consultar' })));
  };

  const alternarCategoria = (chave) => {
    setCategoriasSelecionadas((prev) => (prev.includes(chave) ? prev.filter((c) => c !== chave) : [...prev, chave]));
  };

  const gerarRelatorio = () => {
    if (!token || categoriasSelecionadas.length === 0) return;
    setCarregando(true);
    axios.get(`${API_URL}/dashboard/relatorio`, {
      params: { dias: periodoSelecionado, categorias: categoriasSelecionadas.join(',') },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setDados(r.data)).catch(() => setDados(null)).finally(() => setCarregando(false));
  };

  const periodoLabel = PERIODOS.find((p) => p.id === periodoSelecionado)?.label || '';

  const baixarHtml = () => {
    if (!dados) return;

    const cssCompleto = `
.rel-app{--rel-bg-secundario:#151b24;--rel-bg-elevado:#1b2330;--rel-linha:rgba(255,255,255,.08);--rel-borda:rgba(255,255,255,.10);--rel-tinta:#eef2f8;--rel-suave:#97a3b5;--rel-fraca:#64707f;--rel-marca:#6172f3;--rel-verde:#22c55e;--rel-ambar:#f59e0b;--rel-vermelho:#ef4444;--rel-s1:#3987e5;--rel-s2:#d95926;--rel-s3:#199e70;--rel-s4:#c98500;--rel-s5:#d55181;--rel-s6:#7c3aed;font-family:Arial,sans-serif;background:#0b0f16;padding:24px;}
.rel-faixa-nav{position:sticky;top:0;z-index:20;background:var(--rel-bg-secundario);border:1px solid var(--rel-borda);border-radius:12px;padding:12px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px;}
.rel-faixa-nav b{font-size:13px;color:var(--rel-tinta);}
.rel-pill{font-size:11.5px;color:var(--rel-suave);background:var(--rel-bg-elevado);border:1px solid var(--rel-borda);border-radius:999px;padding:5px 12px;cursor:pointer;user-select:none;}
.rel-pill.ativa{background:rgba(97,114,243,.15);border-color:var(--rel-marca);color:var(--rel-marca);}
.rel-acoes{margin-left:auto;display:flex;gap:8px;}
.rel-btn{font:600 12.5px inherit;border-radius:8px;padding:8px 14px;cursor:pointer;border:1px solid var(--rel-borda);background:var(--rel-marca);color:#fff;}
.rel-doc{max-width:980px;margin:0 auto;}
.rel-pagina{background:var(--rel-bg-secundario);border:1px solid var(--rel-borda);border-radius:18px;padding:40px 44px;margin-bottom:22px;box-shadow:0 20px 50px rgba(0,0,0,.25);color:var(--rel-tinta);}
.rel-pagina.rel-oculta{display:none;}
.rel-num-pagina{text-align:right;font-size:11px;color:var(--rel-fraca);margin-top:18px;}
.rel-capa{min-height:480px;display:flex;flex-direction:column;justify-content:space-between;}
.rel-selo-marca{display:inline-flex;align-items:center;gap:10px;font-weight:800;font-size:15px;}
.rel-quadrado{width:30px;height:30px;border-radius:9px;background:var(--rel-marca);display:grid;place-items:center;color:#fff;font-size:13px;}
.rel-meio{margin:auto 0;}
.rel-tag{display:inline-block;font-size:12px;font-weight:700;color:var(--rel-marca);background:rgba(97,114,243,.15);border:1px solid rgba(97,114,243,.3);border-radius:7px;padding:5px 12px;margin-bottom:18px;text-transform:uppercase;}
.rel-capa h1{font-size:30px;margin:0 0 12px;font-weight:800;max-width:620px;}
.rel-periodo{font-size:15px;color:var(--rel-suave);margin-bottom:4px;}
.rel-cliente{font-size:13px;color:var(--rel-fraca);}
.rel-rodape-capa{display:flex;justify-content:space-between;font-size:12px;color:var(--rel-fraca);border-top:1px solid var(--rel-linha);padding-top:18px;}
.rel-sec-cabecalho{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:26px;border-bottom:1px solid var(--rel-linha);padding-bottom:16px;}
.rel-titulo{font-size:20px;font-weight:800;}
.rel-sub{font-size:12.5px;color:var(--rel-suave);margin-top:4px;}
.rel-badge-sec{font-size:11px;font-weight:700;color:var(--rel-suave);background:var(--rel-bg-elevado);border:1px solid var(--rel-borda);border-radius:7px;padding:5px 10px;}
.rel-kpi-grade{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:26px;}
.rel-kpi{background:var(--rel-bg-elevado);border:1px solid var(--rel-borda);border-radius:12px;padding:16px 18px;}
.rel-rot{font-size:12px;color:var(--rel-suave);margin-bottom:8px;}
.rel-val{font-size:24px;font-weight:800;}
.rel-val.bom{color:var(--rel-verde);}.rel-val.ruim{color:var(--rel-vermelho);}.rel-val.mid{color:var(--rel-ambar);}
.rel-graf-grid-2{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;margin-bottom:22px;}
.rel-graf-grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:22px;}
.rel-caixa{background:var(--rel-bg-elevado);border:1px solid var(--rel-borda);border-radius:12px;padding:16px 18px;}
.rel-titulo-mini{font-size:12.5px;font-weight:600;margin-bottom:2px;}
.rel-sub-mini{font-size:11px;color:var(--rel-fraca);margin-bottom:12px;}
.rel-caixa svg{width:100%;display:block;}
.rel-legenda{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:10px;font-size:11.5px;color:var(--rel-suave);}
.rel-legenda span{display:inline-flex;align-items:center;gap:6px;}
.rel-legenda i{width:9px;height:9px;border-radius:3px;display:inline-block;}
.rel-donut-wrap{display:flex;align-items:center;gap:18px;}
.rel-donut-legenda{flex:1;display:flex;flex-direction:column;gap:8px;}
.rel-item{display:flex;align-items:center;gap:8px;font-size:12.5px;}
.rel-item b{margin-left:auto;}
.rel-donut-legenda i{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
.rel-ranking-item{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:13px;border-bottom:1px solid var(--rel-linha);}
.rel-pos{width:19px;height:19px;border-radius:5px;background:var(--rel-linha);color:var(--rel-suave);font-size:10.5px;font-weight:700;display:grid;place-items:center;flex-shrink:0;}
.rel-eq{flex:1;font-weight:600;}
.rel-texto-auto{font-size:13.5px;line-height:1.6;color:var(--rel-suave);background:var(--rel-bg-elevado);border:1px solid var(--rel-borda);border-left:3px solid var(--faixa,var(--rel-marca));border-radius:8px;padding:14px 16px;margin:20px 0;}
.rel-texto-auto b{color:var(--rel-tinta);}
.rel-cat-header{display:flex;align-items:center;gap:16px;margin-bottom:26px;padding-bottom:20px;border-bottom:1px solid var(--rel-linha);}
.rel-cat-header .rel-nome{font-size:20px;font-weight:800;}
.rel-cat-header .rel-media{margin-left:auto;text-align:right;}
.rel-cat-header .rel-num{font-size:28px;font-weight:800;color:var(--faixa);}
.rel-evt-linha{display:grid;grid-template-columns:88px 18px 1fr auto;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--rel-linha);font-size:12.5px;}
.rel-evt-hora{color:var(--rel-suave);}
.rel-evt-ponto{width:8px;height:8px;border-radius:50%;background:var(--faixa);}
.rel-badge-evt{font-size:10.5px;font-weight:700;padding:4px 9px;border-radius:6px;}
.rel-badge-evt.critico{color:var(--rel-vermelho);background:rgba(239,68,68,.15);}
.rel-badge-evt.atencao{color:var(--rel-ambar);background:rgba(245,158,11,.15);}
.rel-badge-evt.bom{color:var(--rel-verde);background:rgba(34,197,94,.15);}
.rel-tabela-anexo{width:100%;border-collapse:collapse;font-size:12px;}
.rel-tabela-anexo th{text-align:left;font-size:11px;color:var(--rel-fraca);padding:8px 10px;border-bottom:1px solid var(--rel-borda);}
.rel-tabela-anexo td{padding:9px 10px;border-bottom:1px solid var(--rel-linha);}
.rel-pt-faixa{display:inline-flex;align-items:center;gap:6px;font-weight:600;}
.rel-pt-faixa i{width:8px;height:8px;border-radius:50%;}
`;

    const secoes = [{ id: 'geral', label: 'Geral' }];
    Object.entries(dados.categorias).forEach(([chave, info]) => secoes.push({ id: chave, label: info.nome }));
    if (dados.acessos) secoes.push({ id: 'acessos', label: 'Acessos à Internet' });
    secoes.push({ id: 'anexo', label: 'Anexo' });

    const pills = secoes.map((s, i) => `<span class="rel-pill${i === 0 ? ' ativa' : ''}" data-aba="${s.id}">${s.label}</span>`).join('');

    let htmlCapa = `<div class="rel-pagina" data-secao="geral">
      <div class="rel-selo-marca"><span class="rel-quadrado">E</span> E-OPS · Elcop</div>
      <div class="rel-meio">
        <span class="rel-tag">Relatório · ${periodoLabel}</span>
        <h1>Relatório de Disponibilidade e Incidentes</h1>
        <div class="rel-periodo">${periodoLabel}</div>
        <div class="rel-cliente">${categoriasSelecionadas.map(nomeCat).join(', ')}</div>
      </div>
      <div class="rel-rodape-capa"><span>Gerado automaticamente pelo E-OPS</span><span>Gerado em ${formatarDataHora(dados.gerado_em)}</span></div>
    </div>`;

    const deltasValidos = Object.values(dados.categorias)
      .filter((info) => info.mediaAnterior !== null && info.mediaAnterior !== undefined)
      .map((info) => info.media - info.mediaAnterior);
    const deltaGeral = deltasValidos.length ? deltasValidos.reduce((a, b) => a + b, 0) / deltasValidos.length : null;
    const deltaGeralHtml = deltaGeral !== null
      ? `<div style="font-size:10px;color:${deltaGeral >= 0 ? '#22c55e' : '#ef4444'};margin-top:4px;">${deltaGeral >= 0 ? '▲' : '▼'} ${Math.abs(deltaGeral).toFixed(1)}% vs. período anterior</div>`
      : '';

    const donutGeralHtml = gerarDonut([
      { valor: dados.severidade.critico, cor: 'var(--rel-vermelho)' },
      { valor: dados.severidade.atencao, cor: 'var(--rel-ambar)' },
      { valor: dados.severidade.bom, cor: 'var(--rel-verde)' },
    ]).map((seg) => `<circle cx="55" cy="55" r="46" fill="none" stroke="${seg.cor}" stroke-width="14" stroke-dasharray="${seg.comprimento} ${seg.circunferencia}" stroke-dashoffset="${seg.offset}" transform="rotate(-90 55 55)"/>`).join('');

    const equipamentoTop = dados.ranking[0];

    let htmlResumo = `<div class="rel-pagina" data-secao="geral">
      <div class="rel-sec-cabecalho"><div><div class="rel-titulo">Resumo geral</div></div></div>
      <div class="rel-kpi-grade">
        <div class="rel-kpi"><div class="rel-rot">Uptime médio geral</div><div class="rel-val ${classeFaixa(dados.resumo.uptimeGeral)}">${dados.resumo.uptimeGeral}%</div>${deltaGeralHtml}</div>
        <div class="rel-kpi"><div class="rel-rot">Total de incidentes</div><div class="rel-val">${dados.resumo.totalIncidentes}</div></div>
        <div class="rel-kpi"><div class="rel-rot">Total de eventos</div><div class="rel-val">${dados.eventos.length}</div></div>
        <div class="rel-kpi"><div class="rel-rot">Categorias saudáveis</div><div class="rel-val mid">${dados.resumo.categoriasSaudaveis} de ${dados.resumo.totalCategorias}</div></div>
      </div>
      <div class="rel-kpi-grade">
        <div class="rel-kpi"><div class="rel-rot">Melhor desempenho</div><div class="rel-val bom" style="font-size:16px;">${dados.resumo.melhorCategoria || '—'}</div><div style="font-size:11px;color:var(--rel-suave);margin-top:2px;">${dados.resumo.melhorCategoriaValor ?? '—'}%</div></div>
        <div class="rel-kpi"><div class="rel-rot">Pior desempenho</div><div class="rel-val ruim" style="font-size:16px;">${dados.resumo.piorCategoria || '—'}</div><div style="font-size:11px;color:var(--rel-suave);margin-top:2px;">${dados.resumo.piorCategoriaValor ?? '—'}%</div></div>
        <div class="rel-kpi"><div class="rel-rot">Equipamento mais problemático</div><div class="rel-val" style="font-size:16px;">${equipamentoTop ? equipamentoTop.equipamento : '—'}</div><div style="font-size:11px;color:var(--rel-vermelho);margin-top:2px;">${equipamentoTop ? equipamentoTop.ocorrencias + 'x ocorrências' : '—'}</div></div>
      </div>
      <div class="rel-caixa">
        <div class="rel-titulo-mini">Eventos por severidade — ${dados.eventos.length} no total</div>
        <div class="rel-donut-wrap">
          <svg viewBox="0 0 110 110" style="width:100px;flex-shrink:0;"><circle cx="55" cy="55" r="46" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="14"/>${donutGeralHtml}<text x="55" y="52" text-anchor="middle" font-size="18" font-weight="700" fill="var(--rel-tinta)">${dados.eventos.length}</text><text x="55" y="66" text-anchor="middle" font-size="8" fill="var(--rel-suave)">eventos</text></svg>
          <div class="rel-donut-legenda">
            <div class="rel-item"><i style="background:var(--rel-vermelho)"></i>Críticos<b>${dados.severidade.critico}</b></div>
            <div class="rel-item"><i style="background:var(--rel-ambar)"></i>Atenção<b>${dados.severidade.atencao}</b></div>
            <div class="rel-item"><i style="background:var(--rel-verde)"></i>Resolvidos<b>${dados.severidade.bom}</b></div>
          </div>
        </div>
      </div>
      <div class="rel-texto-auto" style="--faixa:var(--rel-marca)">No geral, as categorias selecionadas mantiveram <b>${dados.resumo.uptimeGeral}% de disponibilidade</b> no período. O destaque negativo foi <b>${dados.resumo.piorCategoria || '—'}</b>, com ${dados.resumo.piorCategoriaValor ?? '—'}% de uptime.</div>
    </div>`;

    let htmlCategorias = Object.entries(dados.categorias).map(([chave, info]) => {
      const cor = corFaixa(info.media);
      const delta = info.mediaAnterior !== null && info.mediaAnterior !== undefined ? info.media - info.mediaAnterior : null;
      const eventosCat = eventosPorCategoria(info.nome);
      const sevCat = { critico: 0, atencao: 0, bom: 0 };
      eventosCat.forEach((e) => { if (sevCat[e.tipo] !== undefined) sevCat[e.tipo] += 1; });
      const donutCatHtml = gerarDonut([
        { valor: sevCat.critico, cor: 'var(--rel-vermelho)' },
        { valor: sevCat.atencao, cor: 'var(--rel-ambar)' },
        { valor: sevCat.bom, cor: 'var(--rel-verde)' },
      ], 34).map((seg) => `<circle cx="42" cy="42" r="34" fill="none" stroke="${seg.cor}" stroke-width="12" stroke-dasharray="${seg.comprimento} ${seg.circunferencia}" stroke-dashoffset="${seg.offset}" transform="rotate(-90 42 42)"/>`).join('');

      const contagem = {};
      eventosCat.filter((e) => e.tipo === 'critico').forEach((e) => {
        const nomeEquip = e.mensagem.split(' ').slice(0, 2).join(' ');
        contagem[nomeEquip] = (contagem[nomeEquip] || 0) + 1;
      });
      const rankingLocal = Object.entries(contagem).sort((a, b) => b[1] - a[1]).slice(0, 5);
      const rankingHtml = rankingLocal.length
        ? rankingLocal.map(([nome, qtd], i) => `<div class="rel-ranking-item"><span class="rel-pos">${i + 1}</span><span class="rel-eq">${nome}</span><span class="rel-qtd" style="color:var(--rel-vermelho)">${qtd}x</span></div>`).join('')
        : `<div style="font-size:11px;color:var(--rel-fraca);">Nenhuma ocorrência crítica nesta categoria.</div>`;

      const timelineHtml = eventosCat.length
        ? eventosCat.slice(0, 8).map((ev) => `<div class="rel-evt-linha" style="--faixa:${cor}"><span class="rel-evt-hora">${formatarDataCurta(ev.criado_em)}</span><span class="rel-evt-ponto"></span><span class="rel-evt-texto">${ev.mensagem}</span></div>`).join('')
        : `<div style="font-size:11px;color:var(--rel-fraca);">Nenhum evento nesta categoria.</div>`;

      return `<div class="rel-pagina rel-oculta" data-secao="${chave}" style="--faixa:${cor}">
        <div class="rel-cat-header">
          <div class="rel-nome">${info.nome}</div>
          <div class="rel-media"><div class="rel-num">${info.media}%</div><div class="rel-rot">uptime médio</div></div>
        </div>
        <div class="rel-texto-auto"><b>${info.nome}</b> apresentou ${info.media}% de uptime no período${delta !== null ? ` (variação de ${delta.toFixed(1)} pontos vs. período anterior)` : ''}.</div>
        <div class="rel-caixa">
          <div class="rel-titulo-mini">Distribuição de eventos nesta categoria</div>
          <div class="rel-donut-wrap">
            <svg viewBox="0 0 84 84" style="width:80px;flex-shrink:0;"><circle cx="42" cy="42" r="34" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="12"/>${donutCatHtml}<text x="42" y="39" text-anchor="middle" font-size="14" font-weight="700" fill="var(--rel-tinta)">${sevCat.critico + sevCat.atencao + sevCat.bom}</text><text x="42" y="51" text-anchor="middle" font-size="7" fill="var(--rel-suave)">eventos</text></svg>
            <div class="rel-donut-legenda">
              <div class="rel-item"><i style="background:var(--rel-vermelho)"></i>Crítico<b>${sevCat.critico}</b></div>
              <div class="rel-item"><i style="background:var(--rel-ambar)"></i>Atenção<b>${sevCat.atencao}</b></div>
              <div class="rel-item"><i style="background:var(--rel-verde)"></i>Resolvido<b>${sevCat.bom}</b></div>
            </div>
          </div>
        </div>
        <div class="rel-caixa"><div class="rel-titulo-mini">Ranking de equipamentos problemáticos</div>${rankingHtml}</div>
        <div class="rel-caixa"><div class="rel-titulo-mini">Linha do tempo de eventos</div>${timelineHtml}</div>
      </div>`;
    }).join('');

    let htmlAcessos = '';
    if (dados.acessos) {
      const ac = dados.acessos;
      const paletaAc = ['var(--rel-marca)', 'var(--rel-verde)', 'var(--rel-ambar)', 'var(--rel-vermelho)', 'var(--rel-s2)', 'var(--rel-s3)', 'var(--rel-s4)', 'var(--rel-s5)'];
      const totalTrafegoTexto = formatarBytesRel(ac.resumo.volume_total_bytes);
      const donutAcHtml = gerarDonut((ac.top_sites || []).map((s, i) => ({
        valor: s.volume_bytes,
        cor: paletaAc[i % paletaAc.length],
      })), 42).map((seg) => `<circle cx="55" cy="55" r="42" fill="none" stroke="${seg.cor}" stroke-width="14" stroke-dasharray="${seg.comprimento} ${seg.circunferencia}" stroke-dashoffset="${seg.offset}" transform="rotate(-90 55 55)"/>`).join('');
      const legendaAcHtml = (ac.top_sites || []).map((s, i) => `<div class="rel-item"><i style="background:${paletaAc[i % paletaAc.length]}"></i>${s.categoria}<b>${s.percentual}%</b></div>`).join('');
      const linhaTabelaAc = (r) => `<tr><td>${r.hostname}</td><td>${formatarBytesRel(r.volume_bytes)}</td><td>${r.categoria_principal || '—'}</td></tr>`;
      htmlAcessos = `<div class="rel-pagina rel-oculta" data-secao="acessos">
        <div class="rel-sec-cabecalho"><div><div class="rel-titulo">Acessos à internet</div><div class="rel-sub">Resumo de navegação capturado no período</div></div></div>
        <div class="rel-kpi-grade" style="grid-template-columns:repeat(3,1fr);">
          <div class="rel-kpi"><div class="rel-rot">Volume total trafegado</div><div class="rel-val" style="font-size:18px;">${totalTrafegoTexto}</div></div>
          <div class="rel-kpi"><div class="rel-rot">Categoria mais acessada</div><div class="rel-val" style="font-size:18px;">${ac.resumo.categoria_mais_acessada || '—'}</div></div>
          <div class="rel-kpi"><div class="rel-rot">Dispositivos monitorados</div><div class="rel-val" style="font-size:18px;">${ac.resumo.dispositivos_monitorados}</div></div>
        </div>
        <div class="rel-caixa">
          <div class="rel-titulo-mini">Top categorias acessadas na rede</div>
          <div class="rel-donut-wrap">
            <svg viewBox="0 0 110 110" style="width:100px;flex-shrink:0;"><circle cx="55" cy="55" r="42" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="14"/>${donutAcHtml}<text x="55" y="51" text-anchor="middle" font-size="${totalTrafegoTexto.length <= 7 ? 14 : 11}" font-weight="700" fill="var(--rel-tinta)">${totalTrafegoTexto}</text><text x="55" y="65" text-anchor="middle" font-size="7" fill="var(--rel-suave)">tráfego</text></svg>
            <div class="rel-donut-legenda">${legendaAcHtml}</div>
          </div>
        </div>
        <div style="margin-top:18px;">
          <div class="rel-titulo-mini" style="margin-bottom:8px;">Top 10 dispositivos por volume</div>
          <table class="rel-tabela-anexo"><thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead><tbody>${(ac.ranking_geral || []).map(linhaTabelaAc).join('')}</tbody></table>
        </div>
        <div style="margin-top:18px;">
          <div class="rel-titulo-mini" style="margin-bottom:8px;">Top 10 — uso não corporativo (lazer)</div>
          <table class="rel-tabela-anexo"><thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead><tbody>${(ac.ranking_pessoal || []).map(linhaTabelaAc).join('')}</tbody></table>
        </div>
      </div>`;
    }
    let htmlAnexo = `<div class="rel-pagina rel-oculta" data-secao="anexo">
      <div class="rel-sec-cabecalho"><div><div class="rel-titulo">Anexo — todos os eventos do período</div></div></div>
      <table class="rel-tabela-anexo"><thead><tr><th>Data/hora</th><th>Evento</th><th>Severidade</th></tr></thead><tbody>
        ${dados.eventos.slice(0, 200).map((ev) => `<tr><td>${formatarDataHora(ev.criado_em)}</td><td>${ev.mensagem}</td><td><span class="rel-pt-faixa"><i style="background:${ev.tipo === 'critico' ? 'var(--rel-vermelho)' : ev.tipo === 'atencao' ? 'var(--rel-ambar)' : 'var(--rel-verde)'}"></i>${ev.tipo}</span></td></tr>`).join('')}
      </tbody></table>
    </div>`;

    const script = `
document.querySelectorAll('.rel-pill').forEach(function(pill) {
  pill.addEventListener('click', function() {
    var aba = pill.getAttribute('data-aba');
    document.querySelectorAll('.rel-pill').forEach(function(p) { p.classList.remove('ativa'); });
    pill.classList.add('ativa');
    document.querySelectorAll('.rel-pagina').forEach(function(pag) {
      pag.classList.toggle('rel-oculta', pag.getAttribute('data-secao') !== aba);
    });
  });
});
`;

    const htmlFinal = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório E-Ops</title><style>${cssCompleto}</style></head>
<body class="rel-app">
  <div class="rel-faixa-nav"><b>Relatório · ${periodoLabel}</b>${pills}</div>
  <div class="rel-doc">${htmlCapa}${htmlResumo}${htmlCategorias}${htmlAcessos}${htmlAnexo}</div>
  <script>${script}</script>
</body></html>`;

    const blob = new Blob([htmlFinal], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio-eops-${periodoSelecionado}dias.html`;
    a.click();
    URL.revokeObjectURL(url);
  };



  if (!dados) {
    return (
      <div className="rel-app">
        <h2 className="page-title">Relatórios</h2>
        <div className="rel-faixa-nav">
          <b>Configurar relatório</b>
          <div className="rel-acoes">
            <select className="rel-periodo-select" value={periodoSelecionado} onChange={(e) => setPeriodoSelecionado(e.target.value)}>
              {PERIODOS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '20px' }}>
          {CATEGORIAS_DISPONIVEIS.map((c) => (
            <div key={c.chave} className={`rel-pill ${categoriasSelecionadas.includes(c.chave) ? 'ativa' : ''}`} onClick={() => alternarCategoria(c.chave)}>
              {c.label}
            </div>
          ))}
        </div>
        <div className="rel-btn rel-btn-primario" style={{ display: 'inline-flex' }} onClick={gerarRelatorio}>
          {carregando ? 'Gerando...' : 'Visualizar Relatório'}
        </div>
      </div>
    );
  }

  const nomeCat = (chave) => CATEGORIAS_DISPONIVEIS.find((c) => c.chave === chave)?.label || chave;

  // As mensagens reais dos eventos usam o singular ("Servidor X ficou offline",
  // "Backup de Y falhou"), mas os nomes de categoria sao plural - por isso o
  // mapeamento explicito abaixo, em vez de tentar derivar o singular por regra.
  const PALAVRA_CHAVE_POR_CATEGORIA = {
    'Servidores': 'Servidor',
    'Access Points': 'Access Point',
    'Links de Rede': 'Link',
    'VPNs': 'VPN',
    'VLANs': 'VLAN',
    'Backups': 'Backup',
  };
  const eventosPorCategoria = (nomeCategoria) => {
    const palavraChave = PALAVRA_CHAVE_POR_CATEGORIA[nomeCategoria] || nomeCategoria;
    return dados.eventos.filter((e) => e.mensagem.includes(palavraChave));
  };

  const totalEventos = dados.eventos.length;
  const totalDuracaoTexto = `${dados.severidade.critico} crítico${dados.severidade.critico !== 1 ? 's' : ''}`;

  const equipamentoMaisProblematico = dados.ranking[0];

  const donutGeral = gerarDonut([
    { label: 'Críticos', valor: dados.severidade.critico, cor: 'var(--rel-vermelho)' },
    { label: 'Atenção', valor: dados.severidade.atencao, cor: 'var(--rel-ambar)' },
    { label: 'Resolvidos', valor: dados.severidade.bom, cor: 'var(--rel-verde)' },
  ]);

  return (
    <div className="rel-app">
      <h2 className="page-title">Relatórios</h2>

      <div className="rel-faixa-nav">
        <b>Relatório · {periodoLabel}</b>
        {CATEGORIAS_DISPONIVEIS.filter((c) => categoriasSelecionadas.includes(c.chave)).map((c) => (
          <span className="rel-pill ativa" key={c.chave}>{c.label}</span>
        ))}
        <div className="rel-acoes">
          <div className="rel-btn rel-btn-secundario" onClick={() => setDados(null)}>← Voltar aos filtros</div>
          <div className="rel-btn rel-btn-primario" onClick={async () => {
            const resp = await axios.get(`${API_URL}/dashboard/relatorio/pdf`, {
              params: { dias: periodoSelecionado, categorias: categoriasSelecionadas.join(','), periodo_label: periodoLabel },
              headers: { Authorization: `Bearer ${token}` },
              responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
            const a = document.createElement('a');
            a.href = url;
            a.download = 'relatorio-eops.pdf';
            a.click();
            window.URL.revokeObjectURL(url);
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 15V3M7 10l5 5 5-5" /><path d="M20 21H4" /></svg>
            Baixar PDF
          </div>
          <div className="rel-btn rel-btn-secundario" onClick={baixarHtml}>
            Baixar HTML
          </div>
        </div>
      </div>

      <div className="rel-doc">
        {/* CAPA */}
        <div className="rel-pagina rel-capa">
          <div className="rel-selo-marca"><span className="rel-quadrado">E</span> E-OPS · Elcop</div>
          <div className="rel-meio">
            <span className="rel-tag">Relatório · {periodoLabel}</span>
            <h1>Relatório de Disponibilidade e Incidentes</h1>
            <div className="rel-periodo">{periodoLabel}</div>
            <div className="rel-cliente">{categoriasSelecionadas.map(nomeCat).join(', ')}</div>
          </div>
          <div className="rel-rodape-capa">
            <span>Gerado automaticamente pelo E-OPS</span>
            <span>Gerado em {formatarDataHora(dados.gerado_em)}</span>
          </div>
        </div>

        {/* RESUMO GERAL */}
        <div className="rel-pagina">
          <div className="rel-sec-cabecalho">
            <div>
              <div className="rel-titulo">Resumo geral</div>
              <div className="rel-sub">Visão consolidada das categorias selecionadas no período</div>
            </div>
            <span className="rel-badge-sec">1 de {(Object.keys(dados.categorias).length + 2 + (dados.acessos ? 2 : 0))}</span>
          </div>

          <div className="rel-kpi-grade">
            <div className="rel-kpi">
              <div className="rel-rot">Uptime médio geral</div>
              <div className={`rel-val ${classeFaixa(dados.resumo.uptimeGeral)}`}>{dados.resumo.uptimeGeral}%</div>
            </div>
            <div className="rel-kpi">
              <div className="rel-rot">Total de incidentes</div>
              <div className="rel-val">{dados.resumo.totalIncidentes}</div>
            </div>
            <div className="rel-kpi">
              <div className="rel-rot">Total de eventos</div>
              <div className="rel-val">{totalEventos}</div>
            </div>
            <div className="rel-kpi">
              <div className="rel-rot">Categorias saudáveis</div>
              <div className="rel-val mid">{dados.resumo.categoriasSaudaveis} de {dados.resumo.totalCategorias}</div>
            </div>
            {dados.acessos && (
              <div className="rel-kpi">
                <div className="rel-rot">Volume de acessos (internet)</div>
                <div className="rel-val">{formatarBytesRel(dados.acessos.resumo.volume_total_bytes)}</div>
              </div>
            )}
          </div>

          <div className="rel-graf-grid-2">
            <div className="rel-caixa">
              <div className="rel-titulo-mini">Uptime por categoria</div>
              <div className="rel-sub-mini">% de disponibilidade ao longo do período</div>
              <svg viewBox="0 0 460 140">
                <line x1="10" y1="20" x2="450" y2="20" stroke="rgba(255,255,255,.06)" strokeDasharray="2 4" />
                <line x1="10" y1="70" x2="450" y2="70" stroke="rgba(255,255,255,.06)" strokeDasharray="2 4" />
                <line x1="10" y1="120" x2="450" y2="120" stroke="rgba(255,255,255,.12)" />
                {Object.entries(dados.categorias).map(([chave, info], idx) => {
                  const cor = CATEGORIAS_DISPONIVEIS.find((c) => c.chave === chave)?.cor || '#6172f3';
                  const { path } = gerarLinhaSVG(info.serie, cor);
                  return path ? <path key={chave} d={path} fill="none" stroke={cor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /> : null;
                })}
              </svg>
              <div className="rel-legenda">
                {CATEGORIAS_DISPONIVEIS.filter((c) => categoriasSelecionadas.includes(c.chave)).map((c) => (
                  <span key={c.chave}><i style={{ background: c.cor }} />{c.label}</span>
                ))}
              </div>
            </div>

            <div className="rel-caixa">
              <div className="rel-titulo-mini">Eventos por severidade</div>
              <div className="rel-sub-mini">Total no período: {totalEventos} eventos</div>
              <div className="rel-donut-wrap">
                <svg viewBox="0 0 120 120" style={{ width: '110px', flexShrink: 0 }}>
                  <circle cx="60" cy="60" r="46" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="16" />
                  {donutGeral.map((seg, idx) => (
                    <circle
                      key={idx} cx="60" cy="60" r="46" fill="none"
                      stroke={seg.cor} strokeWidth="16"
                      strokeDasharray={`${seg.comprimento} ${seg.circunferencia}`}
                      strokeDashoffset={seg.offset}
                      transform="rotate(-90 60 60)"
                    />
                  ))}
                  <text x="60" y="56" textAnchor="middle" fontSize="20" fontWeight="700" fill="var(--rel-tinta)">{totalEventos}</text>
                  <text x="60" y="72" textAnchor="middle" fontSize="9" fill="var(--rel-suave)">eventos</text>
                </svg>
                <div className="rel-donut-legenda">
                  <div className="rel-item"><i style={{ background: 'var(--rel-vermelho)' }} />Críticos<b>{dados.severidade.critico}</b></div>
                  <div className="rel-item"><i style={{ background: 'var(--rel-ambar)' }} />Atenção<b>{dados.severidade.atencao}</b></div>
                  <div className="rel-item"><i style={{ background: 'var(--rel-verde)' }} />Resolvidos<b>{dados.severidade.bom}</b></div>
                </div>
              </div>
            </div>
          </div>

          <div className="rel-graf-grid-3">
            <div className="rel-caixa">
              <div className="rel-titulo-mini">Melhor desempenho</div>
              <div className="rel-sub-mini">{dados.resumo.melhorCategoria}</div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--rel-verde)' }}>{dados.resumo.melhorCategoriaValor}%</div>
            </div>
            <div className="rel-caixa">
              <div className="rel-titulo-mini">Pior desempenho</div>
              <div className="rel-sub-mini">{dados.resumo.piorCategoria}</div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--rel-vermelho)' }}>{dados.resumo.piorCategoriaValor}%</div>
            </div>
            <div className="rel-caixa">
              <div className="rel-titulo-mini">Equipamento mais problemático</div>
              <div className="rel-sub-mini">Geral, todas as categorias</div>
              <div style={{ fontSize: '16px', fontWeight: 800 }}>
                {equipamentoMaisProblematico?.equipamento || '—'}
                {equipamentoMaisProblematico && <span style={{ fontSize: '11px', color: 'var(--rel-vermelho)', fontWeight: 700 }}> · {equipamentoMaisProblematico.ocorrencias}x</span>}
              </div>
            </div>
          </div>

          <div className="rel-texto-auto" style={{ '--faixa': 'var(--rel-marca)' }}>
            No geral, as categorias selecionadas mantiveram <b>{dados.resumo.uptimeGeral}% de disponibilidade</b> no período.
            {dados.resumo.piorCategoria && <> O destaque negativo foi <b>{dados.resumo.piorCategoria}</b>, com {dados.resumo.piorCategoriaValor}% de uptime.</>}
            {equipamentoMaisProblematico && <> O equipamento <b>{equipamentoMaisProblematico.equipamento}</b> foi o mais problemático, com {equipamentoMaisProblematico.ocorrencias} ocorrências.</>}
          </div>

          <div className="rel-num-pagina">Página 1</div>
        </div>

        {/* PAGINA POR CATEGORIA */}
        {Object.entries(dados.categorias).map(([chave, info], idx) => {
          const cor = corFaixa(info.media);
          const delta = info.mediaAnterior !== null && info.mediaAnterior !== undefined ? info.media - info.mediaAnterior : null;
          const eventosCat = eventosPorCategoria(info.nome);
          const rankingCat = dados.ranking.filter((r) => r.equipamento && info.nome && true).slice(0, 4);
          return (
            <div className="rel-pagina" style={{ '--faixa': cor }} key={chave}>
              <div className="rel-sec-cabecalho">
                <div><div className="rel-titulo">Detalhe por categoria</div><div className="rel-sub">{info.nome}</div></div>
                <span className="rel-badge-sec">{idx + 2} de {(Object.keys(dados.categorias).length + 2 + (dados.acessos ? 2 : 0))}</span>
              </div>

              <div className="rel-cat-header">
                <span className="rel-cat-icone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{ICONES_CATEGORIA[chave]}</svg></span>
                <div className="rel-nomes">
                  <div className="rel-nome">{info.nome}</div>
                  <div className="rel-sub">{eventosCat.length} evento{eventosCat.length !== 1 ? 's' : ''} no período</div>
                </div>
                <div className="rel-media">
                  <div className="rel-num">{info.media}%</div>
                  <div className="rel-rot">uptime médio</div>
                  {delta !== null && (
                    <div className={`rel-delta ${delta >= 0 ? 'melhorou' : 'piorou'}`}>
                      {delta >= 0 ? '↑' : '↓'} {Math.abs(delta).toFixed(1)}% vs. anterior
                    </div>
                  )}
                </div>
              </div>

              <div className="rel-graf-grid-2">
                <div className="rel-caixa">
                  <div className="rel-titulo-mini">Evolução do uptime</div>
                  <div className="rel-sub-mini">{periodoLabel}</div>
                  <svg viewBox="0 0 460 140">
                    <line x1="10" y1="20" x2="450" y2="20" stroke="rgba(255,255,255,.06)" strokeDasharray="2 4" />
                    <line x1="10" y1="70" x2="450" y2="70" stroke="rgba(255,255,255,.06)" strokeDasharray="2 4" />
                    {(() => {
                      const { path, area } = gerarLinhaSVG(info.serie, cor);
                      return path ? (
                        <>
                          <path d={area} fill={cor} opacity="0.1" />
                          <path d={path} fill="none" stroke={cor} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                        </>
                      ) : <text x="200" y="70" fill="var(--rel-fraca)" fontSize="12">Sem dados suficientes</text>;
                    })()}
                  </svg>
                </div>
                <div className="rel-caixa">
                  <div className="rel-titulo-mini">Distribuição de eventos</div>
                  <div className="rel-sub-mini">Nesta categoria</div>
                  {(() => {
                    const sevCat = { critico: 0, atencao: 0, bom: 0 };
                    eventosCat.forEach((e) => { if (sevCat[e.tipo] !== undefined) sevCat[e.tipo] += 1; });
                    const donutCat = gerarDonut([
                      { valor: sevCat.critico, cor: 'var(--rel-vermelho)' },
                      { valor: sevCat.atencao, cor: 'var(--rel-ambar)' },
                      { valor: sevCat.bom, cor: 'var(--rel-verde)' },
                    ], 38);
                    return (
                      <div className="rel-donut-wrap">
                        <svg viewBox="0 0 100 100" style={{ width: '90px', flexShrink: 0 }}>
                          <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="14" />
                          {donutCat.map((seg, i) => (
                            <circle key={i} cx="50" cy="50" r="38" fill="none" stroke={seg.cor} strokeWidth="14"
                              strokeDasharray={`${seg.comprimento} ${seg.circunferencia}`} strokeDashoffset={seg.offset}
                              transform="rotate(-90 50 50)" />
                          ))}
                          <text x="50" y="47" textAnchor="middle" fontSize="16" fontWeight="700" fill="var(--rel-tinta)">{sevCat.critico + sevCat.atencao + sevCat.bom}</text>
                          <text x="50" y="60" textAnchor="middle" fontSize="8" fill="var(--rel-suave)">eventos</text>
                        </svg>
                        <div className="rel-donut-legenda">
                          <div className="rel-item"><i style={{ background: 'var(--rel-vermelho)' }} />Crítico<b>{sevCat.critico}</b></div>
                          <div className="rel-item"><i style={{ background: 'var(--rel-ambar)' }} />Atenção<b>{sevCat.atencao}</b></div>
                          <div className="rel-item"><i style={{ background: 'var(--rel-verde)' }} />Resolvido<b>{sevCat.bom}</b></div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>

              <div className="rel-caixa" style={{ marginBottom: '18px' }}>
                <div className="rel-titulo-mini">Ranking de equipamentos problemáticos</div>
                <div className="rel-sub-mini">Nesta categoria</div>
                {(() => {
                  const contagem = {};
                  eventosCat.filter((e) => e.tipo === 'critico').forEach((e) => {
                    const nomeEquip = e.mensagem.split(' ').slice(0, 2).join(' ');
                    contagem[nomeEquip] = (contagem[nomeEquip] || 0) + 1;
                  });
                  const rankingLocal = Object.entries(contagem).sort((a, b) => b[1] - a[1]).slice(0, 4);
                  if (rankingLocal.length === 0) return <div style={{ fontSize: '12px', color: 'var(--rel-fraca)' }}>Nenhuma ocorrência crítica nesta categoria.</div>;
                  return rankingLocal.map(([nome, qtd], i) => (
                    <div className="rel-ranking-item" key={i}>
                      <span className="rel-pos">{i + 1}</span>
                      <span className="rel-eq">{nome}</span>
                      <span className="rel-qtd" style={{ color: 'var(--rel-vermelho)' }}>{qtd} ocorrência{qtd > 1 ? 's' : ''}</span>
                    </div>
                  ));
                })()}
              </div>

              <div className="rel-texto-auto">
                <b>{info.nome}</b> apresentou {info.media}% de uptime no período{delta !== null && Math.abs(delta) >= 0.5 && <> — {delta > 0 ? 'uma melhora' : 'uma queda'} de {Math.abs(delta).toFixed(1)} pontos percentuais em relação ao período anterior</>}.
                {eventosCat.filter((e) => e.tipo === 'critico').length > 0
                  ? <> Foram registrados {eventosCat.filter((e) => e.tipo === 'critico').length} evento(s) crítico(s) nessa categoria.</>
                  : <> Nenhum evento crítico registrado nessa categoria no período.</>}
              </div>

              {eventosCat.length > 0 && (
                <>
                  <div className="rel-titulo-mini" style={{ marginBottom: '10px' }}>Linha do tempo de eventos</div>
                  {eventosCat.slice(0, 8).map((ev) => (
                    <div className="rel-evt-linha" key={ev.id}>
                      <span className="rel-evt-hora">{formatarDataCurta(ev.criado_em)}</span>
                      <span className="rel-evt-ponto" style={{ background: ev.tipo === 'critico' ? 'var(--rel-vermelho)' : ev.tipo === 'atencao' ? 'var(--rel-ambar)' : 'var(--rel-verde)' }} />
                      <span className="rel-evt-texto">{ev.mensagem}{ev.detalhes && <span className="rel-meta">{ev.detalhes}</span>}</span>
                      <span className={`rel-badge-evt ${ev.tipo}`}>{ev.tipo === 'critico' ? 'Crítico' : ev.tipo === 'atencao' ? 'Atenção' : 'Resolvido'}</span>
                    </div>
                  ))}
                </>
              )}

              <div className="rel-num-pagina">Página {idx + 2}</div>
            </div>
          );
        })}
        {dados.acessos && (() => {
          const ac = dados.acessos;
          const paletaAc = ['var(--rel-marca)', 'var(--rel-verde)', 'var(--rel-ambar)', 'var(--rel-vermelho)', 'var(--rel-s2)', 'var(--rel-s3)', 'var(--rel-s4)', 'var(--rel-s5)'];
          const donutAc = gerarDonut((ac.top_sites || []).map((s, i) => ({
            valor: s.volume_bytes,
            cor: paletaAc[i % paletaAc.length],
          })), 38);
          const linhaDispositivo = (r) => {
            const naoResolvido = r.hostname === 'Desconhecido';
            const ehVpn = !!(r.ip && r.ip.startsWith('10.8.'));
            const nomeRevelado = nomesRevelados[r.mac];
            return (
              <tr key={r.mac}>
                <td>
                  {r.hostname}
                  {naoResolvido && ehVpn && podeRevelarIdentidade && (
                    nomeRevelado ? (
                      <span style={{ marginLeft: '6px', opacity: 0.8 }}>({nomeRevelado})</span>
                    ) : (
                      <span
                        style={{ marginLeft: '6px', cursor: 'pointer', textDecoration: 'underline dotted', fontSize: '10.5px', opacity: 0.7 }}
                        onClick={() => revelarIdentidadeAcessos(r.mac, r.ip)}
                      >
                        revelar identidade
                      </span>
                    )
                  )}
                </td>
                <td>{formatarBytesRel(r.volume_bytes)}</td>
                <td>{r.categoria_principal || '—'}</td>
              </tr>
            );
          };
          const paginaAtualDonut = Object.keys(dados.categorias).length + 2;
          const paginaAtualTabelas = paginaAtualDonut + 1;
          const totalPaginasCalc = Object.keys(dados.categorias).length + 2 + (dados.acessos ? 2 : 0);
          return (
            <>
              <div className="rel-pagina">
                <div className="rel-sec-cabecalho">
                  <div><div className="rel-titulo">Acessos à internet</div><div className="rel-sub">Resumo de navegação capturado no período</div></div>
                  <span className="rel-badge-sec">{paginaAtualDonut} de {totalPaginasCalc}</span>
                </div>
                <div className="rel-kpi-grade">
                  <div className="rel-kpi">
                    <div className="rel-rot">Volume total trafegado</div>
                    <div className="rel-val">{formatarBytesRel(ac.resumo.volume_total_bytes)}</div>
                  </div>
                  <div className="rel-kpi">
                    <div className="rel-rot">Categoria mais acessada</div>
                    <div className="rel-val">{ac.resumo.categoria_mais_acessada || '—'}</div>
                  </div>
                  <div className="rel-kpi">
                    <div className="rel-rot">Dispositivos monitorados</div>
                    <div className="rel-val">{ac.resumo.dispositivos_monitorados}</div>
                  </div>
                </div>
                <div className="rel-caixa">
                  <div className="rel-titulo-mini">Top categorias acessadas na rede</div>
                  <div className="rel-donut-wrap">
                    <svg viewBox="0 0 100 100" style={{ width: '90px', flexShrink: 0 }}>
                      <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="14" />
                      {donutAc.map((seg, i) => (
                        <circle key={i} cx="50" cy="50" r="38" fill="none" stroke={seg.cor} strokeWidth="14"
                          strokeDasharray={`${seg.comprimento} ${seg.circunferencia}`} strokeDashoffset={seg.offset}
                          transform="rotate(-90 50 50)" />
                      ))}
                      <text x="50" y="47" textAnchor="middle" fontSize={formatarBytesRel(ac.resumo.volume_total_bytes).length <= 7 ? '13' : '10'} fontWeight="700" fill="var(--rel-tinta)">
                        {formatarBytesRel(ac.resumo.volume_total_bytes)}
                      </text>
                      <text x="50" y="59" textAnchor="middle" fontSize="6" fill="var(--rel-fraca)">tráfego</text>
                    </svg>
                    <div className="rel-donut-legenda">
                      {(ac.top_sites || []).map((s, i) => (
                        <div className="rel-item" key={i}>
                          <i style={{ background: paletaAc[i % paletaAc.length] }} />
                          {s.categoria}<b>{s.percentual}%</b>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="rel-num-pagina">Página {paginaAtualDonut}</div>
              </div>
              <div className="rel-pagina">
                <div className="rel-sec-cabecalho">
                  <div><div className="rel-titulo">Acessos à internet — rankings</div><div className="rel-sub">Dispositivos com maior volume trafegado no período</div></div>
                  <span className="rel-badge-sec">{paginaAtualTabelas} de {totalPaginasCalc}</span>
                </div>
                <div style={{ marginTop: '4px', overflowX: 'auto' }}>
                  <div className="rel-titulo-mini" style={{ marginBottom: '6px' }}>Top 10 dispositivos por volume</div>
                  <table className="rel-tabela-anexo">
                    <thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead>
                    <tbody>{ac.ranking_geral.map(linhaDispositivo)}</tbody>
                  </table>
                </div>
                <div style={{ marginTop: '18px', overflowX: 'auto' }}>
                  <div className="rel-titulo-mini" style={{ marginBottom: '6px' }}>Top 10 — uso não corporativo (lazer)</div>
                  <table className="rel-tabela-anexo">
                    <thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead>
                    <tbody>{ac.ranking_pessoal.map(linhaDispositivo)}</tbody>
                  </table>
                </div>
                <div className="rel-num-pagina">Página {paginaAtualTabelas}</div>
              </div>
            </>
          );
        })()}

        {/* ANEXO */}
        <div className="rel-pagina">
          <div className="rel-sec-cabecalho">
            <div><div className="rel-titulo">Anexo — todos os eventos do período</div><div className="rel-sub">{totalEventos} eventos, ordenados cronologicamente</div></div>
            <span className="rel-badge-sec">{(Object.keys(dados.categorias).length + 2 + (dados.acessos ? 2 : 0))} de {(Object.keys(dados.categorias).length + 2 + (dados.acessos ? 2 : 0))}</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="rel-tabela-anexo">
              <thead><tr><th>Data/hora</th><th>Evento</th><th>Detalhes</th><th>Severidade</th></tr></thead>
              <tbody>
                {dados.eventos.slice(0, 200).map((ev) => (
                  <tr key={ev.id}>
                    <td>{formatarDataHora(ev.criado_em)}</td>
                    <td>{ev.mensagem}</td>
                    <td>{ev.detalhes || '—'}</td>
                    <td>
                      <span className="rel-pt-faixa">
                        <i style={{ background: ev.tipo === 'critico' ? 'var(--rel-vermelho)' : ev.tipo === 'atencao' ? 'var(--rel-ambar)' : 'var(--rel-verde)' }} />
                        {ev.tipo === 'critico' ? 'Crítico' : ev.tipo === 'atencao' ? 'Atenção' : 'Resolvido'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Relatorios;
