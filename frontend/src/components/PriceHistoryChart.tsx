import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getPriceHistory } from "../api";
import type { PriceHistoryPoint } from "../types";

interface ChartPoint {
  date: string;
  ts: number;
  loose?: number;
  cib?: number;
  new?: number;
  graded?: number;
}

function PriceHistoryChart({ gameId }: { gameId: number }) {
  const [points, setPoints] = useState<PriceHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getPriceHistory(gameId)
      .then(setPoints)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [gameId]);

  if (loading) return <p className="loading">Chargement de l'historique...</p>;

  // On ne garde que les points PriceCharting (cote collector)
  const pcPoints = points.filter((p) => p.source === "pricecharting");
  if (pcPoints.length < 2) {
    return (
      <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
        Pas assez de points pour afficher un historique (au moins 2 scrapings nécessaires).
      </p>
    );
  }

  const data: ChartPoint[] = pcPoints.map((p) => {
    const d = new Date(p.scraped_at);
    return {
      date: d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }),
      ts: d.getTime(),
      loose: parseFloat(p.price),
      cib: p.cib_price ? parseFloat(p.cib_price) : undefined,
      new: p.new_price ? parseFloat(p.new_price) : undefined,
      graded: p.graded_price ? parseFloat(p.graded_price) : undefined,
    };
  });

  return (
    <div style={{ width: "100%", height: 300, marginTop: "0.5rem" }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 12 }} />
          <YAxis
            stroke="#888"
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
            formatter={(v: number) => `$${v.toFixed(2)}`}
          />
          <Legend wrapperStyle={{ fontSize: "0.85rem" }} />
          <Line
            type="monotone"
            dataKey="loose"
            stroke="#4ade80"
            strokeWidth={2}
            name="Loose"
            dot={{ r: 3 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="cib"
            stroke="#60a5fa"
            strokeWidth={2}
            name="CIB"
            dot={{ r: 3 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="new"
            stroke="#fbbf24"
            strokeWidth={2}
            name="Neuf"
            dot={{ r: 3 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="graded"
            stroke="#f472b6"
            strokeWidth={2}
            name="Gradé"
            dot={{ r: 3 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PriceHistoryChart;
