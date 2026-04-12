import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, getTopExpensive, type TopGame } from "../api";
import type { Stats } from "../types";

const PLATFORMS = [
  { value: "", label: "Toutes" },
  { value: "neo", label: "Neo Geo" },
  { value: "nes", label: "NES" },
  { value: "snes", label: "SNES" },
  { value: "n64", label: "N64" },
  { value: "gba", label: "GBA" },
  { value: "saturn", label: "Saturn" },
  { value: "ps1", label: "PlayStation" },
  { value: "dreamcast", label: "Dreamcast" },
];

function formatCHF(value: string | null) {
  if (!value) return "-";
  return `${parseFloat(value).toLocaleString("fr-CH", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} CHF`;
}

function formatUSD(value: string | null) {
  if (!value) return "";
  return `$${parseFloat(value).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [topGames, setTopGames] = useState<TopGame[]>([]);
  const [platform, setPlatform] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats().then(setStats).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    getTopExpensive(platform || undefined)
      .then(setTopGames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [platform]);

  return (
    <div>
      <h1 style={{ marginBottom: "0.5rem" }}>Video Games Bourse</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>
        Cotes et prix des jeux retro collector
      </p>

      {stats && (
        <div className="stats">
          <div className="stat-card">
            <div className="stat-card__value">{stats.games_count.toLocaleString("fr-FR")}</div>
            <div className="stat-card__label">
              Jeux PAL vérifiés
              {stats.games_count_total && (
                <span style={{ color: "var(--text-secondary)", fontSize: "0.75rem", display: "block" }}>
                  sur {stats.games_count_total.toLocaleString("fr-FR")} importés
                </span>
              )}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-card__value">{stats.machines_count}</div>
            <div className="stat-card__label">Consoles</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__value">{topGames.length}</div>
            <div className="stat-card__label">Jeux cotes</div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem", marginTop: "2rem" }}>
        <h2>Top 200 - Jeux les plus chers</h2>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            padding: "0.4rem 0.8rem",
            fontSize: "0.9rem",
          }}
        >
          {PLATFORMS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="loading">Chargement...</p>
      ) : topGames.length === 0 ? (
        <p className="loading">Aucun prix disponible. Lancez le scraping PriceCharting.</p>
      ) : (
        <table className="top-table">
          <thead>
            <tr>
              <th>#</th>
              <th></th>
              <th>Jeu</th>
              <th>Console</th>
              <th>Loose</th>
              <th>Complet (CIB)</th>
              <th>Neuf</th>
              <th>Grade</th>
              <th>Ricardo</th>
            </tr>
          </thead>
          <tbody>
            {topGames.map((game, i) => (
              <tr key={game.id}>
                <td className="top-table__rank">{i + 1}</td>
                <td>
                  {game.cover_url && (
                    <img className="top-table__cover" src={game.cover_url} alt="" />
                  )}
                </td>
                <td>
                  <Link to={`/games/${game.id}`} className="top-table__title">
                    {game.title}
                  </Link>
                </td>
                <td>
                  <div className="tags">
                    {game.machines.map((m) => (
                      <span key={m} className="tag">{m}</span>
                    ))}
                  </div>
                </td>
                <td className="top-table__price top-table__price--loose">
                  {formatCHF(game.loose_price_chf)}
                  <span style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                    {formatUSD(game.loose_price)}
                  </span>
                </td>
                <td className="top-table__price">
                  {formatCHF(game.cib_price_chf)}
                  {game.cib_price && (
                    <span style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                      {formatUSD(game.cib_price)}
                    </span>
                  )}
                </td>
                <td className="top-table__price top-table__price--new">
                  {formatCHF(game.new_price_chf)}
                </td>
                <td className="top-table__price top-table__price--graded">
                  {game.graded_price ? formatUSD(game.graded_price) : "-"}
                </td>
                <td className="top-table__price top-table__price--ricardo">
                  {game.ricardo_price ? (
                    <a href={game.ricardo_url || "#"} target="_blank" rel="noopener noreferrer">
                      {parseFloat(game.ricardo_price).toFixed(0)} CHF
                      {game.ricardo_bids !== null && game.ricardo_bids > 0 && (
                        <span className="top-table__bids"> ({game.ricardo_bids})</span>
                      )}
                    </a>
                  ) : (
                    <span style={{ color: "var(--text-secondary)" }}>-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default HomePage;
