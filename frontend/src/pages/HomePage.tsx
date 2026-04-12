import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, getOpportunities } from "../api";
import type { Opportunity, Stats } from "../types";

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

function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [deals, setDeals] = useState<Opportunity[]>([]);
  const [platform, setPlatform] = useState("");
  const [minDiscount, setMinDiscount] = useState("30");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats().then(setStats).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { limit: "100", min_discount: minDiscount };
    if (platform) params.platform = platform;
    getOpportunities(params)
      .then(setDeals)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [platform, minDiscount]);

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
              Jeux PAL
              {stats.games_count_total && (
                <span style={{ color: "var(--text-secondary)", fontSize: "0.75rem", display: "block" }}>
                  sur {stats.games_count_total.toLocaleString("fr-FR")} importes
                </span>
              )}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-card__value">{stats.machines_count}</div>
            <div className="stat-card__label">Consoles</div>
          </div>
          <div className="stat-card">
            <div className="stat-card__value">{deals.length}</div>
            <div className="stat-card__label">Deals en cours</div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem", marginTop: "2rem", flexWrap: "wrap" }}>
        <h2>Meilleures affaires</h2>
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
        <select
          value={minDiscount}
          onChange={(e) => setMinDiscount(e.target.value)}
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            padding: "0.4rem 0.8rem",
            fontSize: "0.9rem",
          }}
        >
          <option value="10">-10%</option>
          <option value="20">-20%</option>
          <option value="30">-30%</option>
          <option value="50">-50%</option>
        </select>
      </div>

      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
        Annonces Ricardo et eBay sous la cote PriceCharting (comparaison par condition : loose vs loose, CIB vs CIB).
      </p>

      {loading ? (
        <p className="loading">Chargement...</p>
      ) : deals.length === 0 ? (
        <p className="loading">Aucun deal trouve avec ces criteres.</p>
      ) : (
        <table className="top-table">
          <thead>
            <tr>
              <th>#</th>
              <th></th>
              <th>Jeu</th>
              <th>Console</th>
              <th>Etat</th>
              <th>Prix annonce</th>
              <th>Cote</th>
              <th>Decote</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d, i) => (
              <tr key={`${d.listing_id}-${i}`}>
                <td className="top-table__rank">{i + 1}</td>
                <td>
                  {d.cover_url && (
                    <img className="top-table__cover" src={d.cover_url} alt="" />
                  )}
                </td>
                <td>
                  <Link to={`/games/${d.game_id}`} className="top-table__title">
                    {d.title}
                  </Link>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 2 }}>
                    <a href={d.listing_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--text-secondary)" }}>
                      {d.listing_title.length > 50 ? d.listing_title.slice(0, 50) + "..." : d.listing_title}
                    </a>
                  </div>
                </td>
                <td>
                  <span className="tag">{d.platform_slug.toUpperCase()}</span>
                </td>
                <td>
                  <span className="tag" style={{
                    background: d.listing_condition === "cib" ? "#1d4ed8"
                      : d.listing_condition === "new" ? "#15803d"
                      : d.listing_condition === "graded" ? "#7e22ce"
                      : "var(--bg-secondary)",
                    color: "white",
                    fontSize: "0.75rem",
                  }}>
                    {d.listing_condition || "loose"}
                  </span>
                </td>
                <td className="top-table__price">
                  {d.listing_price_chf.toFixed(0)} CHF
                  {d.listing_currency !== "CHF" && (
                    <span style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                      {d.listing_price_eur.toFixed(0)} EUR
                    </span>
                  )}
                </td>
                <td className="top-table__price">
                  {Math.round(d.ref_price_usd * 0.79)} CHF
                  <span style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                    ${d.ref_price_usd.toFixed(0)} {d.ref_source}
                  </span>
                </td>
                <td>
                  <span
                    className="tag"
                    style={{
                      background: d.discount_percent >= 70 ? "#dc2626"
                        : d.discount_percent >= 50 ? "#ea580c"
                        : d.discount_percent >= 30 ? "#16a34a"
                        : "#0891b2",
                      color: "white",
                      fontWeight: "bold",
                    }}
                  >
                    -{d.discount_percent.toFixed(0)}%
                  </span>
                </td>
                <td>
                  <a href={d.listing_url} target="_blank" rel="noopener noreferrer">
                    <span className={`tag tag--source tag--${d.listing_source}`}>
                      {d.listing_source}
                    </span>
                  </a>
                  {d.bid_count > 0 && (
                    <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", marginLeft: 4 }}>
                      {d.bid_count} ench.
                    </span>
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
