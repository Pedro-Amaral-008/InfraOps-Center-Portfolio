import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './Estabilidade.css';

const API_URL = '';

const ORDEM_CATEGORIAS = ['Servidores', 'Access Points', 'Links de Rede', 'Backups', 'Impressoras'];
const CATEGORIAS_OPERACAO = ['Servidores', 'Links de Rede', 'Backups'];
const CATEGORIAS_LOCAL = ['Access Points', 'Impressoras'];

const CHAVE_PARA_NOME = {
  servidores: 'Servidores',
  access_points: 'Access Points',
  links: 'Links de Rede',
  backups: 'Backups',
  impressoras: 'Impressoras',
};
const NOME_PARA_CHAVE = Object.fromEntries(Object.entries(CHAVE_PARA_NOME).map(([k, v]) => [v, k]));

const ICONES = {
  'Servidores': <><rect x="3" y="4" width="18" height="6" rx="1.6" /><rect x="3" y="14" width="18" height="6" rx="1.6" /><path d="M7 7h.01M7 17h.01" /></>,
  'Access Points': <><path d="M2.5 8.5a16 16 0 0 1 19 0" /><path d="M6 12.5a11 11 0 0 1 12 0" /><path d="M9.5 16.4a6 6 0 0 1 5 0" /><circle cx="12" cy="20" r="1.1" fill="currentColor" stroke="none" /></>,
  'Links de Rede': <><circle cx="18" cy="5" r="2.6" /><circle cx="6" cy="12" r="2.6" /><circle cx="18" cy="19" r="2.6" /><path d="M8.3 10.7l7.4-4.3M8.3 13.3l7.4 4.3" /></>,
  'Backups': <><path d="M6.5 18.5a4 4 0 0 1 .4-8 5.6 5.6 0 0 1 10.6 1.4 3.6 3.6 0 0 1-.7 6.6" /><path d="M12 21v-8M9 15.5l3-3 3 3" /></>,
  'Impressoras': <><path d="M7 9V3h10v6" /><rect x="3" y="9" width="18" height="7" rx="1.8" /><rect x="7" y="14" width="10" height="7" rx="1.2" /></>,
};

function letraDoDia(data) {
  switch (data.getDay()) {
    case 0: return 'Dom';
    case 1: return 'Seg';
    case 2: return 'Ter';
    case 3: return 'Qua';
    case 4: return 'Qui';
    case 5: return 'Sex';
    case 6: return 'Sáb';
    default: return '';
  }
}

// Monta os 7 dias terminando em hoje, na ordem que aparece na tela (mais antigo -> hoje)
function diasSemanaAteHoje() {
  const hoje = new Date();
  const resultado = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(hoje);
    d.setDate(hoje.getDate() - i);
    resultado.push(letraDoDia(d));
  }
  return resultado;
}
const XS = [8, 54.67, 101.33, 148, 194.67, 241.33, 288];
const DURACAO_ANIMACAO_MS = 700;

function faixaDaMedia(media) {
  if (media >= 99) return 'verde';
  if (media >= 90) return 'ambar';
  return 'vermelho';
}

function calcularMedia(valores) {
  const validos = valores.filter((v) => v !== null && v !== undefined);
  if (!validos.length) return 0;
  return validos.reduce((a, b) => a + b, 0) / validos.length;
}

function calcularVariacao14(todos14) {
  const semanaAtual = todos14.slice(-7);
  const semanaAnterior = todos14.slice(0, todos14.length - 7);
  const mediaAtual = calcularMedia(semanaAtual);
  const mediaAnterior = calcularMedia(semanaAnterior);
  const validosAnterior = semanaAnterior.filter((v) => v !== null && v !== undefined);
  if (validosAnterior.length === 0 || mediaAnterior === 0) {
    return { sinal: 'estavel', texto: 'Estável' };
  }
  const delta = ((mediaAtual - mediaAnterior) / mediaAnterior) * 100;
  if (Math.abs(delta) < 0.5) return { sinal: 'estavel', texto: 'Estável' };
  return {
    sinal: delta > 0 ? 'alta' : 'baixa',
    texto: `${Math.abs(delta).toFixed(1).replace('.', ',')}%`,
  };
}

function pisoDoEixo(valores) {
  const v = valores.filter((n) => typeof n === 'number');
  if (!v.length) return 70;
  const min = Math.min(...v);
  const degraus = [70, 40, 10, 0];
  for (let i = 0; i < degraus.length; i++) {
    if (min >= degraus[i] + 2) return degraus[i];
  }
  return 0;
}

function normalizarPara7(diasOriginais) {
  const faltam = Math.max(0, 7 - diasOriginais.length);
  return [...Array(faltam).fill(null), ...diasOriginais.slice(-7)];
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function corDoValor(v) {
  if (v === null || v === undefined) return 'vazio';
  if (v >= 99) return 'verde';
  if (v >= 90) return 'ambar';
  return 'vermelho';
}

function GraficoSVG({ dias, media }) {
  const piso = pisoDoEixo(dias);
  const faixaY = 58 - 10;
  const yDe = (v) => 58 - ((v - piso) / (100 - piso)) * faixaY;

  const ultimoIndice = dias.length - 1;
  const diasSemana = diasSemanaAteHoje();
  const larguraBarra = 26;

  const rotulosY = [];
  for (let i = 0; i <= 3; i++) {
    const v = 100 - i * ((100 - piso) / 3);
    const y = yDe(v);
    rotulosY.push({ y: y.toFixed(2), texto: `${Math.round(v)}%`, textoY: (y + 3).toFixed(2) });
  }

  return (
    <svg className="estab-svg" viewBox="0 0 356 74" role="img" aria-label={`Gráfico de disponibilidade: média de ${media.toFixed(1)}%`}>
      {rotulosY.map((r, idx) => (
        <line className="estab-grade" x1="8" y1={r.y} x2="288" y2={r.y} key={idx} />
      ))}
      {dias.map((v, idx) => {
        const status = corDoValor(v);
        const ehHoje = idx === ultimoIndice;
        const yTopo = v === null ? 54 : yDe(v);
        const altura = Math.max(58 - yTopo, 3);
        return (
          <rect
            key={idx}
            className="estab-barra"
            data-status={status}
            data-hoje={ehHoje ? 'true' : undefined}
            x={XS[idx] - larguraBarra / 2}
            y={yTopo}
            width={larguraBarra}
            height={altura}
            rx="3"
          >
            <title>{`${diasSemana[idx]}${ehHoje ? ' (hoje)' : ''} · ${v === null ? 'sem dados' : v.toFixed(1) + '%'}`}</title>
          </rect>
        );
      })}
      {rotulosY.map((r, idx) => (
        <text className="estab-rotulo-y" x="310" y={r.textoY} key={idx}>{r.texto}</text>
      ))}
      {XS.map((x, idx) => (
        <text className="estab-rotulo-x" x={x} y="72" key={idx}>{diasSemana[idx]}</text>
      ))}
    </svg>
  );
}

function Estabilidade({ token }) {
  const [dados, setDados] = useState({});
  const [diasAnimados, setDiasAnimados] = useState({});
  const ultimoRef = useRef({});
  const animacoesRef = useRef({});

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    const buscar = () => {
      axios.get(`${API_URL}/dashboard/estabilidade-14-dias`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      }).then((r) => setDados(r.data)).catch(() => {});
    };
    buscar();
    const intervalo = setInterval(buscar, 60000);
    // ao sair da aba, para o timer E cancela a requisicao em andamento
    return () => {
      clearInterval(intervalo);
      controller.abort();
    };
  }, [token]);

  useEffect(() => {
    ORDEM_CATEGORIAS.forEach((nome) => {
      const chave = NOME_PARA_CHAVE[nome];
      const info14 = dados[chave];
      if (!info14) return;
      const novos = normalizarPara7(info14.slice(-7));
      const antigos = ultimoRef.current[nome];

      if (!antigos) {
        setDiasAnimados((prev) => ({ ...prev, [nome]: novos }));
        ultimoRef.current[nome] = novos;
        return;
      }

      if (animacoesRef.current[nome]) cancelAnimationFrame(animacoesRef.current[nome]);
      const inicio = performance.now();

      const passo = (agora) => {
        const t = Math.min(1, (agora - inicio) / DURACAO_ANIMACAO_MS);
        const te = easeOutCubic(t);
        const interpolados = novos.map((v, i) => {
          const anterior = antigos[i];
          if (v === null || anterior === null || anterior === undefined) return v;
          return anterior + (v - anterior) * te;
        });
        setDiasAnimados((prev) => ({ ...prev, [nome]: interpolados }));
        if (t < 1) {
          animacoesRef.current[nome] = requestAnimationFrame(passo);
        } else {
          delete animacoesRef.current[nome];
        }
      };
      animacoesRef.current[nome] = requestAnimationFrame(passo);
      ultimoRef.current[nome] = novos;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dados]);

  const renderCategoria = (nome) => {
    const chave = NOME_PARA_CHAVE[nome];
    const info14 = dados[chave];
    const dias = diasAnimados[nome];
    if (!info14 || !dias) return null;

    const media = calcularMedia(dias);
    const faixa = faixaDaMedia(media);
    const variacao = calcularVariacao14(info14);

    return (
      <div className="estab-linha-dados" data-faixa={faixa} key={nome}>
        <div className="estab-categoria">
          <span className="estab-icone" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {ICONES[nome]}
            </svg>
          </span>
          <span className="estab-nome">{nome}</span>
        </div>

        <div className="estab-grafico">
          <GraficoSVG dias={dias} media={media} />
        </div>

        <div className="estab-media">{media.toFixed(1)}%</div>

        {variacao.sinal === 'estavel' ? (
          <span className="estab-variacao" data-sinal="estavel">Estável</span>
        ) : (
          <span className="estab-variacao" data-sinal={variacao.sinal}>
            <svg className="estab-seta" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              {variacao.sinal === 'alta'
                ? <path d="M12 19V5M6 11l6-6 6 6" />
                : <path d="M12 5v14M6 13l6 6 6-6" />}
            </svg>
            {variacao.texto}
          </span>
        )}
      </div>
    );
  };

  const legenda = (
    <footer className="estab-legenda">
      <span className="estab-chave"><i className="estab-bolinha" style={{ '--cor': 'var(--estab-verde)' }} />≥99%</span>
      <span className="estab-chave"><i className="estab-bolinha" style={{ '--cor': 'var(--estab-ambar)' }} />90–98.9%</span>
      <span className="estab-chave"><i className="estab-bolinha" style={{ '--cor': 'var(--estab-vermelho)' }} />&lt;90%</span>
      <span className="estab-chave"><i className="estab-bolinha" data-vazio="true" />sem dados</span>
    </footer>
  );

  return (
    <div className="estab-grupo">
      <section className="estab" aria-labelledby="estab-titulo-operacao">
        <header className="estab-topo">
          <span className="estab-selo" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12h4l3 8 4-16 3 8h4" />
            </svg>
          </span>
          <div className="estab-textos">
            <h2 className="estab-titulo" id="estab-titulo-operacao">Estabilidade da Operação · últimos 7 dias</h2>
            <p className="estab-sub">Infraestrutura crítica — servidores, rede e backups que sustentam o acesso</p>
          </div>
        </header>

        <div className="estab-cabecalho" aria-hidden="true">
          <span>Categoria</span>
          <span>Últimos 7 dias</span>
          <span>Disponibilidade média</span>
          <span style={{ justifySelf: 'end' }}>Variação (7d)</span>
        </div>

        <div className="estab-corpo">
          {CATEGORIAS_OPERACAO.map(renderCategoria)}
        </div>

        {legenda}
      </section>

      <section className="estab" aria-labelledby="estab-titulo-local">
        <header className="estab-topo">
          <span className="estab-selo" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <path d="M9 21v-4a3 3 0 0 1 6 0v4" />
              <path d="M9 8h.01M15 8h.01M9 12h.01M15 12h.01" />
            </svg>
          </span>
          <div className="estab-textos">
            <h2 className="estab-titulo" id="estab-titulo-local">Estabilidade Local · últimos 7 dias</h2>
            <p className="estab-sub">Equipamentos de ponta por unidade — access points e impressoras</p>
          </div>
        </header>

        <div className="estab-cabecalho" aria-hidden="true">
          <span>Categoria</span>
          <span>Últimos 7 dias</span>
          <span>Disponibilidade média</span>
          <span style={{ justifySelf: 'end' }}>Variação (7d)</span>
        </div>

        <div className="estab-corpo">
          {CATEGORIAS_LOCAL.map(renderCategoria)}
        </div>

        {legenda}
      </section>
    </div>
  );
}

export default Estabilidade;
