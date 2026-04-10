import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMachines, getOpportunities } from "../api";
import type { Machine, Opportunity } from "../types";

function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [platform, setPlatform] = useState("");
  const [minDiscount, setMinDiscount] = useState("20");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMachines().then((data) => setMachines(data.results));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { limit: "150", min_discount: minDiscount };
    if (platform) params.platform = platform;
    getOpportunities(params)
      .then(setOpportunities)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [platform, minDiscount]);

  return (
    <div>
      <h1 style={{ marginBottom: "0.5rem" }}>Bonnes affaires</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
        Annonces Ricardo dont le prix (CHF→USD) est sous la cote PriceCharting (CIB ou loose).
      </p>

      <div className="filters" style={{ marginBottom: "1.5rem" }}>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          <option value="">Toutes les plateformes</option>
          {machines.map((m) => (
            <option key={m.id} value={m.slug}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          value={minDiscount}
          onChange={(e) => setMinDiscount(e.target.value)}
        >
          <option value="10">Décote ≥ 10%</option>
          <option value="20">Décote ≥ 20%</option>
          <option value="30">Décote ≥ 30%</option>
          <option value="50">Décote ≥ 50%</option>
        </select>
      </div>

      {loading ? (
        <p className="loading">Recherche d'opportunités...</p>
      ) : opportunities.length === 0 ? (
        <p className="loading">Aucune opportunité trouvée avec ces critères.</p>
      ) : (
        <table className="listings-table">
          <thead>
            <tr>
              <th>Jeu</th>
              <th>Console</th>
              <th>Annonce</th>
              <th>Prix CHF</th>
              <th>Prix EUR</th>
              <th>Cote ($)</th>
              <th>Décote</th>
              <th>Ench.</th>
            </tr>
          </thead>
          <tbody>
            {opportunities.map((o) => (
              <tr key={o.listing_id}>
                <td>
                  <Link to={`/games/${o.game_id}`}>
                    {o.cover_url && (
                      <img
                        src={o.cover_url}
                        alt={o.title}
                        style={{
                          width: 30,
                          height: 30,
                          objectFit: "cover",
                          borderRadius: 4,
                          verticalAlign: "middle",
                          marginRight: 8,
                        }}
                      />
                    )}
                    {o.title}
                  </Link>
                </td>
                <td>
                  <span className="tag">{o.platform_slug.toUpperCase()}</span>
                </td>
                <td>
                  <a href={o.listing_url} target="_blank" rel="noopener noreferrer">
                    {o.listing_title.length > 45
                      ? o.listing_title.slice(0, 45) + "…"
                      : o.listing_title}
                  </a>
                </td>
                <td className="listings-table__price">
                  {o.listing_price_chf.toFixed(0)} CHF
                </td>
                <td className="listings-table__price">
                  {o.listing_price_eur.toFixed(0)} €
                </td>
                <td className="listings-table__price">
                  ${o.ref_price_usd.toFixed(0)}
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.7rem", marginLeft: 4 }}>
                    {o.ref_source}
                  </span>
                </td>
                <td>
                  <span
                    className="tag"
                    style={{
                      background: o.discount_percent >= 50 ? "#16a34a" : "#0891b2",
                      color: "white",
                    }}
                  >
                    -{o.discount_percent.toFixed(0)}%
                  </span>
                </td>
                <td className="listings-table__bids">{o.bid_count || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default OpportunitiesPage;
