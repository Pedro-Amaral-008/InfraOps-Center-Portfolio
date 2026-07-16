import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './MetricChart.css';

function formatarHora(timestamp) {
  const data = new Date(timestamp);
  return data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function MetricChart({ titulo, dados, cor = '#3B9FD1', unidade = '%', altura = 220 }) {
  const dadosFormatados = dados.map((ponto) => ({
    hora: formatarHora(ponto.timestamp),
    valor: ponto.valor,
  }));

  const gradientId = `grad-${titulo.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div className="metric-chart-box">
      <h3 className="metric-chart-title">{titulo}</h3>
      {dadosFormatados.length === 0 ? (
        <div className="metric-chart-empty">Sem dados disponíveis</div>
      ) : (
        <ResponsiveContainer width="100%" height={altura}>
          <AreaChart data={dadosFormatados} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={cor} stopOpacity={0.28} />
                <stop offset="100%" stopColor={cor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,255,255,0.045)" vertical={false} />
            <XAxis
              dataKey="hora"
              stroke="var(--text-tertiary)"
              tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              minTickGap={40}
            />
            <YAxis
              stroke="var(--text-tertiary)"
              tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              unit={unidade}
              width={44}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#16304D',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '10px',
                fontSize: '13px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
                padding: '10px 14px',
              }}
              labelStyle={{ color: 'var(--text-secondary)', marginBottom: '4px', fontSize: '11px' }}
              itemStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
              cursor={{ stroke: 'rgba(255,255,255,0.15)', strokeWidth: 1 }}
            />
            <Area
              type="monotone"
              dataKey="valor"
              stroke={cor}
              strokeWidth={2.25}
              fill={`url(#${gradientId})`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--bg-secondary)' }}
              unit={unidade}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default MetricChart;
