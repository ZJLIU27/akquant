import ReactECharts from 'echarts-for-react';
import { useMemo, useState } from 'react';
import { colors } from '../theme/variables';
import type { DailyResponse } from '../api/client';

interface Props {
  data: DailyResponse | null;
  avgCost: number;
}

function seriesValue(v: number | null): number | null {
  return v == null || Number.isNaN(v) ? null : v;
}

type SubchartId = 'volume' | 'singlePin' | 'brick';

const subchartOptions: Array<{ id: SubchartId; label: string }> = [
  { id: 'volume', label: '成交量' },
  { id: 'singlePin', label: '单针下20' },
  { id: 'brick', label: '砖形图' },
];

export default function DailyChart({ data, avgCost }: Props) {
  const [visibleSubcharts, setVisibleSubcharts] = useState<Record<SubchartId, boolean>>({
    volume: true,
    singlePin: true,
    brick: true,
  });

  const activePanels = useMemo(() => {
    const panels: Array<{ id: 'main' | SubchartId; height: number }> = [{ id: 'main', height: 230 }];
    if (visibleSubcharts.volume) panels.push({ id: 'volume', height: 58 });
    if (visibleSubcharts.singlePin) panels.push({ id: 'singlePin', height: 95 });
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
  const brickOriginal = records.map(r => seriesValue(r.brick));
  const brickBase = records.map(r => seriesValue(r.brick_base));
  const brickDelta = records.map(r => seriesValue(r.brick_delta));
  const brickColors = records.map(r => r.brick_color || colors.red);

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
      data: ['K线', '白线', '黄线', '成本线', '短', '中', '中长', '长', '砖形图'],
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
              onChange={event => setVisibleSubcharts(prev => ({ ...prev, [item.id]: event.target.checked }))}
            />
            {item.label}
          </label>
        ))}
      </div>
      <ReactECharts option={option} style={{ height: chartHeight }} notMerge={true} />
    </div>
  );
}
