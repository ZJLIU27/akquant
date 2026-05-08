import ReactECharts from 'echarts-for-react';
import { colors } from '../theme/variables';
import type { IntradayResponse } from '../api/client';

interface Props {
  data: IntradayResponse | null;
  avgCost: number;
}

export default function IntradayChart({ data, avgCost }: Props) {
  if (!data || !data.data || data.status === 'missing') {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.slate }}>
        分时数据暂无，请在持仓列表页点击"刷新分时"获取
      </div>
    );
  }

  const records = data.data;
  // Find time and price columns
  const timeKey = Object.keys(records[0]).find(k =>
    ['time', '时间', 'datetime', 'date'].includes(k.toLowerCase())
  );
  const priceKey = Object.keys(records[0]).find(k =>
    ['close', 'price', '成交价', '最新价', '现价', '当前价', '收盘', 'current'].includes(k.toLowerCase())
  );

  if (!timeKey || !priceKey) {
    return <div style={{ padding: 40, textAlign: 'center', color: colors.slate }}>数据格式不匹配</div>;
  }

  const times = records.map(r => String(r[timeKey]));
  const prices = records.map(r => Number(r[priceKey]));

  const option = {
    backgroundColor: '#fff',
    grid: { left: 60, right: 30, top: 20, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: times,
      axisLabel: { fontSize: 11, color: colors.slate },
      axisLine: { lineStyle: { color: colors.borderLight } },
    },
    yAxis: {
      type: 'value' as const,
      scale: true,
      axisLabel: { fontSize: 11, color: colors.slate },
      splitLine: { lineStyle: { color: colors.borderLight } },
    },
    series: [
      {
        name: '价格',
        type: 'line' as const,
        data: prices,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: colors.yellow, width: 2 },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(240, 185, 11, 0.3)' },
              { offset: 1, color: 'rgba(240, 185, 11, 0.02)' },
            ],
          },
        },
      },
      ...(avgCost > 0 ? [{
        name: '成本线',
        type: 'line' as const,
        data: new Array(times.length).fill(avgCost),
        symbol: 'none',
        lineStyle: { color: colors.red, width: 1, type: 'dashed' as const },
      }] : []),
    ],
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: colors.dark,
      textStyle: { color: '#fff', fontSize: 12 },
    },
  };

  return <ReactECharts option={option} style={{ height: 300 }} />;
}
