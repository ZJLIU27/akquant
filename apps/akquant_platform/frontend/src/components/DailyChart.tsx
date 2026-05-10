import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { colors } from '../theme/variables';
import type { DailyResponse, Transaction } from '../api/client';

interface Props {
  symbol: string;
  data: DailyResponse | null;
  avgCost: number;
  transactions?: Transaction[];
}

function seriesValue(v: number | null): number | null {
  return v == null || Number.isNaN(v) ? null : v;
}

type SubchartId = 'volume' | 'singlePin' | 'kdj' | 'macd' | 'brick';

const subchartOptions: Array<{ id: SubchartId; label: string }> = [
  { id: 'volume', label: '成交量' },
  { id: 'singlePin', label: '单针下20' },
  { id: 'kdj', label: 'KDJ' },
  { id: 'macd', label: 'MACD' },
  { id: 'brick', label: '砖形图' },
];

const defaultVisibleSubcharts: Record<SubchartId, boolean> = {
  volume: true,
  singlePin: true,
  kdj: true,
  macd: true,
  brick: true,
};

const tradeMarkerColors = {
  buy: '#00E5FF',
  sell: '#FFB000',
  border: '#101828',
};

function tradeTooltip(params: { seriesName: string; marker: string; name: string; data?: { tradePrice?: number; quantity?: number } }) {
  const tradePrice = params.data?.tradePrice;
  const quantity = params.data?.quantity;
  return `${params.marker}${params.seriesName}<br/>${params.name}<br/>${quantity ?? '-'} 股 @ ${tradePrice == null ? '-' : tradePrice.toFixed(4)}`;
}

function storageKey(symbol: string) {
  return `akquant.dailyChart.subcharts.${symbol}`;
}

function loadVisibleSubcharts(symbol: string): Record<SubchartId, boolean> {
  if (typeof window === 'undefined') return { ...defaultVisibleSubcharts };
  try {
    const raw = window.localStorage.getItem(storageKey(symbol));
    if (!raw) return { ...defaultVisibleSubcharts };
    const saved = JSON.parse(raw) as Partial<Record<SubchartId, boolean>>;
    return { ...defaultVisibleSubcharts, ...saved };
  } catch {
    return { ...defaultVisibleSubcharts };
  }
}

export default function DailyChart({ symbol, data, avgCost, transactions = [] }: Props) {
  const [visibleSubcharts, setVisibleSubcharts] = useState<Record<SubchartId, boolean>>(() => loadVisibleSubcharts(symbol));

  useEffect(() => {
    setVisibleSubcharts(loadVisibleSubcharts(symbol));
  }, [symbol]);

  const toggleSubchart = (id: SubchartId, checked: boolean) => {
    setVisibleSubcharts(prev => {
      const next = { ...prev, [id]: checked };
      if (typeof window !== 'undefined') {
        try {
          window.localStorage.setItem(storageKey(symbol), JSON.stringify(next));
        } catch {
          // The chart should remain usable even when browser storage is blocked.
        }
      }
      return next;
    });
  };

  const activePanels = useMemo(() => {
    const panels: Array<{ id: 'main' | SubchartId; height: number }> = [{ id: 'main', height: 230 }];
    if (visibleSubcharts.volume) panels.push({ id: 'volume', height: 58 });
    if (visibleSubcharts.singlePin) panels.push({ id: 'singlePin', height: 95 });
    if (visibleSubcharts.kdj) panels.push({ id: 'kdj', height: 86 });
    if (visibleSubcharts.macd) panels.push({ id: 'macd', height: 86 });
    if (visibleSubcharts.brick) panels.push({ id: 'brick', height: 82 });
    return panels;
  }, [visibleSubcharts]);

  if (!data || !data.data || data.status === 'missing') {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.slate }}>
        日线数据缺失，请先更新日线数据
      </div>
    );
  }

  const records = data.data;
  const dates = records.map(r => r.date);
  const candles = records.map(r => [
    seriesValue(r.open),
    seriesValue(r.close),
    seriesValue(r.low),
    seriesValue(r.high),
  ]);
  const volumes = records.map(r => seriesValue(r.volume));
  const volumeColors = records.map(r => r.volume_color || colors.slate);
  const yellow = records.map(r => seriesValue(r.yellow_line));
  const white = records.map(r => seriesValue(r.white_line));
  const singleShort = records.map(r => seriesValue(r.single_pin_short));
  const singleMid = records.map(r => seriesValue(r.single_pin_mid));
  const singleMidLong = records.map(r => seriesValue(r.single_pin_mid_long));
  const singleLong = records.map(r => seriesValue(r.single_pin_long));
  const kdjK = records.map(r => seriesValue(r.kdj_k));
  const kdjD = records.map(r => seriesValue(r.kdj_d));
  const kdjJ = records.map(r => seriesValue(r.kdj_j));
  const macdDif = records.map(r => seriesValue(r.macd_dif));
  const macdDea = records.map(r => seriesValue(r.macd_dea));
  const macd = records.map(r => seriesValue(r.macd));
  const brickOriginal = records.map(r => seriesValue(r.brick));
  const brickBase = records.map(r => seriesValue(r.brick_base));
  const brickDelta = records.map(r => seriesValue(r.brick_delta));
  const brickColors = records.map(r => r.brick_color || colors.red);
  const macdColors = macd.map(value => (value != null && value >= 0 ? colors.red : colors.green));
  const recordByDate = new Map(records.map(record => [record.date, record]));
  const tradeMarkers = transactions
    .filter(transaction => !transaction.voided && recordByDate.has(transaction.trade_date))
    .map(transaction => {
      const record = recordByDate.get(transaction.trade_date);
      const close = seriesValue(record?.close ?? null);
      const price = close ?? transaction.price;
      return {
        id: transaction.id,
        side: transaction.side,
        value: [transaction.trade_date, price],
        tradePrice: transaction.price,
        quantity: transaction.quantity,
      };
    });
  const buyMarkers = tradeMarkers.filter(marker => marker.side === 'buy');
  const sellMarkers = tradeMarkers.filter(marker => marker.side === 'sell');

  const gridGap = 24;
  let top = 34;
  const grids = activePanels.map(panel => {
    const grid = { left: 58, right: 22, top, height: panel.height };
    top += panel.height + gridGap;
    return grid;
  });
  const chartHeight = top + 30;
  const panelIndex = (id: 'main' | SubchartId) => activePanels.findIndex(panel => panel.id === id);
  const linkedAxis = activePanels.map((_, index) => index);
  const xAxes = activePanels.map((_, i) => ({
    type: 'category' as const,
    data: dates,
    gridIndex: i,
    boundaryGap: true,
    axisLine: { lineStyle: { color: colors.borderLight } },
    axisLabel: { show: i === activePanels.length - 1, color: colors.slate, fontSize: 11 },
    axisTick: { show: false },
  }));
  const yAxes = activePanels.map(panel => {
    if (panel.id === 'singlePin') {
      return {
        type: 'value' as const,
        min: 0,
        max: 100,
        gridIndex: panelIndex(panel.id),
        axisLabel: { color: colors.slate, fontSize: 10 },
        splitLine: { lineStyle: { color: colors.borderLight } },
      };
    }
    if (panel.id === 'kdj') {
      return {
        type: 'value' as const,
        scale: true,
        gridIndex: panelIndex(panel.id),
        axisLabel: { color: colors.slate, fontSize: 10 },
        splitLine: { lineStyle: { color: colors.borderLight } },
      };
    }
    if (panel.id === 'macd') {
      return {
        type: 'value' as const,
        scale: true,
        gridIndex: panelIndex(panel.id),
        axisLabel: { color: colors.slate, fontSize: 10 },
        splitLine: { lineStyle: { color: colors.borderLight } },
      };
    }
    return {
      type: 'value' as const,
      scale: true,
      gridIndex: panelIndex(panel.id),
      axisLabel: { color: colors.slate, fontSize: panel.id === 'main' ? 11 : 10 },
      splitLine: { show: panel.id !== 'volume', lineStyle: { color: colors.borderLight } },
    };
  });

  const series: any[] = [
    {
      name: 'K线',
      type: 'candlestick' as const,
      data: candles,
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      itemStyle: {
        color: colors.red,
        color0: colors.green,
        borderColor: colors.red,
        borderColor0: colors.green,
      },
    },
    {
      name: '白线',
      type: 'line' as const,
      data: white,
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      symbol: 'none',
      lineStyle: { color: colors.white, width: 2, shadowColor: colors.ink, shadowBlur: 2 },
    },
    {
      name: '黄线',
      type: 'line' as const,
      data: yellow,
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      symbol: 'none',
      lineStyle: { color: colors.yellow, width: 2 },
    },
    ...(avgCost > 0 ? [{
      name: '成本线',
      type: 'line' as const,
      data: new Array(dates.length).fill(avgCost),
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      symbol: 'none',
      lineStyle: { color: colors.focusBlue, width: 1, type: 'dashed' as const },
    }] : []),
    {
      name: 'Buy',
      type: 'scatter' as const,
      data: buyMarkers,
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      symbol: 'triangle',
      symbolSize: 17,
      symbolOffset: [0, 10],
      itemStyle: { color: tradeMarkerColors.buy, borderColor: tradeMarkerColors.border, borderWidth: 2 },
      tooltip: {
        formatter: tradeTooltip,
      },
    },
    {
      name: 'Sell',
      type: 'scatter' as const,
      data: sellMarkers,
      xAxisIndex: panelIndex('main'),
      yAxisIndex: panelIndex('main'),
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 17,
      symbolOffset: [0, -10],
      itemStyle: { color: tradeMarkerColors.sell, borderColor: tradeMarkerColors.border, borderWidth: 2 },
      tooltip: {
        formatter: tradeTooltip,
      },
    },
  ];

  if (visibleSubcharts.volume) {
    const index = panelIndex('volume');
    series.push({
      name: '成交量',
      type: 'bar' as const,
      data: volumes,
      xAxisIndex: index,
      yAxisIndex: index,
      itemStyle: {
        color: (params: { dataIndex: number }) => volumeColors[params.dataIndex],
      },
    });
  }

  if (visibleSubcharts.singlePin) {
    const index = panelIndex('singlePin');
    series.push(
      {
        name: '短',
        type: 'line' as const,
        data: singleShort,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.white, width: 1, shadowColor: colors.ink, shadowBlur: 2 },
      },
      {
        name: '中',
        type: 'line' as const,
        data: singleMid,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.yellow, width: 1 },
        markLine: {
          symbol: 'none',
          silent: true,
          lineStyle: { color: colors.green, type: 'dashed' as const, width: 1 },
          data: [{ yAxis: 20 }, { yAxis: 80 }],
          label: { show: false },
        },
      },
      {
        name: '中长',
        type: 'line' as const,
        data: singleMidLong,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: '#C77DFF', width: 1 },
      },
      {
        name: '长',
        type: 'line' as const,
        data: singleLong,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.red, width: 1.5 },
      },
    );
  }

  if (visibleSubcharts.kdj) {
    const index = panelIndex('kdj');
    series.push(
      {
        name: 'K',
        type: 'line' as const,
        data: kdjK,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.yellow, width: 1.2 },
      },
      {
        name: 'D',
        type: 'line' as const,
        data: kdjD,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.focusBlue, width: 1.2 },
        markLine: {
          symbol: 'none',
          silent: true,
          lineStyle: { color: colors.borderLight, type: 'dashed' as const, width: 1 },
          data: [{ yAxis: 20 }, { yAxis: 80 }],
          label: { show: false },
        },
      },
      {
        name: 'J',
        type: 'line' as const,
        data: kdjJ,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.red, width: 1.2 },
      },
    );
  }

  if (visibleSubcharts.macd) {
    const index = panelIndex('macd');
    series.push(
      {
        name: 'MACD',
        type: 'bar' as const,
        data: macd,
        xAxisIndex: index,
        yAxisIndex: index,
        itemStyle: {
          color: (params: { dataIndex: number }) => macdColors[params.dataIndex],
        },
      },
      {
        name: 'DIF',
        type: 'line' as const,
        data: macdDif,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.yellow, width: 1.2 },
      },
      {
        name: 'DEA',
        type: 'line' as const,
        data: macdDea,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { color: colors.focusBlue, width: 1.2 },
      },
    );
  }

  if (visibleSubcharts.brick) {
    const index = panelIndex('brick');
    series.push(
      {
        name: '砖形图',
        type: 'line' as const,
        data: brickOriginal,
        xAxisIndex: index,
        yAxisIndex: index,
        symbol: 'none',
        lineStyle: { width: 0, opacity: 0 },
        itemStyle: { opacity: 0 },
      },
      {
        name: '砖形图基准',
        type: 'bar' as const,
        stack: 'brick',
        data: brickBase,
        xAxisIndex: index,
        yAxisIndex: index,
        itemStyle: { color: 'transparent', borderColor: 'transparent' },
        emphasis: { disabled: true },
        tooltip: { show: false },
      },
      {
        name: '砖形图(变动)',
        type: 'bar' as const,
        stack: 'brick',
        data: brickDelta,
        xAxisIndex: index,
        yAxisIndex: index,
        itemStyle: {
          color: (params: { dataIndex: number }) => brickColors[params.dataIndex],
        },
      },
    );
  }

  const option = {
    backgroundColor: '#fff',
    animation: false,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'cross' as const },
      backgroundColor: colors.dark,
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 12 },
    },
    legend: {
      top: 0,
      left: 8,
      itemWidth: 10,
      itemHeight: 8,
      textStyle: { color: colors.slate, fontSize: 11 },
      data: ['K线', '白线', '黄线', '成本线', 'Buy', 'Sell', '短', '中', '中长', '长', 'K', 'D', 'J', 'MACD', 'DIF', 'DEA', '砖形图'],
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside' as const, xAxisIndex: linkedAxis, start: 35, end: 100 },
      { type: 'slider' as const, xAxisIndex: linkedAxis, bottom: 0, height: 18, start: 35, end: 100 },
    ],
    series,
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {subchartOptions.map(item => (
          <label
            key={item.id}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 10px',
              border: `1px solid ${colors.borderLight}`,
              borderRadius: 6,
              color: colors.ink,
              fontSize: 12,
              cursor: 'pointer',
              background: visibleSubcharts[item.id] ? '#FFF8D6' : colors.white,
            }}
          >
            <input
              type="checkbox"
              checked={visibleSubcharts[item.id]}
              onChange={event => toggleSubchart(item.id, event.target.checked)}
            />
            {item.label}
          </label>
        ))}
      </div>
      <ReactECharts option={option} style={{ height: chartHeight }} notMerge={true} />
    </div>
  );
}
