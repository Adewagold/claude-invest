"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, AreaSeries, type IChartApi, type Time } from "lightweight-charts";
import type { PortfolioSnapshot } from "@/lib/types";

interface PortfolioChartProps {
  snapshots: PortfolioSnapshot[];
}

export function PortfolioChart({ snapshots }: PortfolioChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || snapshots.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      timeScale: {
        timeVisible: true,
        borderColor: "#27272a",
      },
      rightPriceScale: {
        borderColor: "#27272a",
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#10b981",
      topColor: "rgba(16, 185, 129, 0.3)",
      bottomColor: "rgba(16, 185, 129, 0.0)",
      lineWidth: 2,
    });

    // Build data: reverse (oldest first), deduplicate timestamps, ensure ascending order
    const seen = new Set<number>();
    const data = snapshots
      .slice()
      .reverse()
      .reduce<{ time: Time; value: number }[]>((acc, s) => {
        const ts = Math.floor(
          new Date(s.timestamp.replace(" ", "T") + "Z").getTime() / 1000
        );
        if (!isNaN(ts) && !seen.has(ts)) {
          seen.add(ts);
          acc.push({ time: ts as Time, value: s.total_value });
        }
        return acc;
      }, [])
      .sort((a, b) => (a.time as number) - (b.time as number));

    if (data.length === 0) return;
    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [snapshots]);

  return <div ref={chartContainerRef} className="w-full" />;
}
