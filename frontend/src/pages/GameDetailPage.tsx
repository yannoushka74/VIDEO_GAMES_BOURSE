import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getGame } from "../api";
import type { Game, Price } from "../types";
import PriceChartingIcon from "../components/PriceChartingIcon";
import PriceHistoryChart from "../components/PriceHistoryChart";

function formatPrice(value: string | null, currency: string) {
  if (!value) return null;
  const num = parseFloat(value).toFixed(2);
  return currency === "USD" ? `$${num}` : `${num} ${currency}`;
}

function PriceLine({ label, usd, chf, cls }: { label: string; usd: string | null; chf: string | null; cls?: string }) {
  if (!usd) return null;
  return (
    <div className="price-card__collector-item">
      <span className="price-card__collector-label">{label}</span>
      <span className={`price-card__collector-value ${cls || ""}`}>
        {formatPrice(usd, "USD")}
        {chf && (
          <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginLeft: 6 }}>
            ({formatPrice(chf, "CHF")})
          </span>
        )}
      </span>
    </div>
  );
}

function PriceChartingCard({ p }: { p: Price }) {
  return (
    <a
      href={p.product_url}
      target="_blank"
      rel="noopener noreferrer"
      className="price-card"
    >
      <div className="price-card__source">
        <PriceChartingIcon size={20} />
        <span>PriceCharting</span>
        {p.region && (
          <span className={`price-card__region price-card__region--${p.region}`}>
            {p.region.toUpperCase()}
          </span>
        )}
      </div>
      <div className="price-card__collector">
        <PriceLine label="Loose" usd={p.price} chf={p.price_chf} />
        <PriceLine label="Complet (CIB)" usd={p.cib_price} chf={p.cib_price_chf} />
        <PriceLine label="Neuf scelle" usd={p.new_price} chf={p.new_price_chf} cls="price-card__collector-value--high" />
        <PriceLine label="Grade (WATA/VGA)" usd={p.graded_price} chf={p.graded_price_chf} cls="price-card__collector-value--premium" />
      </div>
      {(p.box_only_price || p.manual_only_price) && (
        <div className="price-card__extras">
          {p.box_only_price && <span>Boite seule : {formatPrice(p.box_only_price, p.currency)}</span>}
          {p.manual_only_price && <span>Manuel seul : {formatPrice(p.manual_only_price, p.currency)}</span>}
        </div>
      )}
    </a>
  );
}

function GenericPriceCard({ p }: { p: Price }) {
  const sourceLabel = p.source.charAt(0).toUpperCase() + p.source.slice(1);
  return (
    <a
      href={p.product_url}
      target="_blank"
      rel="noopener noreferrer"
      className="price-card"
    >
      <div className="price-card__source">
        <span>{sourceLabel}</span>
      </div>
      <div className="price-card__details">
        <span className="price-card__price">{formatPrice(p.price, p.currency)}</span>
        {p.old_price && (
          <span className="price-card__old">{formatPrice(p.old_price, p.currency)}</span>
        )}
        {p.discount_percent && (
          <span className="price-card__discount">-{p.discount_percent}%</span>
        )}
      </div>
      <div className="price-card__meta">
        {p.rating && (
          <span className="price-card__rating">
            {"★".repeat(Math.round(parseFloat(p.rating)))} {p.rating}/5
            {p.review_count !== null && ` (${p.review_count.toLocaleString("fr-FR")} avis)`}
          </span>
        )}
        {p.availability && (
          <span className={`price-card__avail ${p.availability.toLowerCase().includes("stock") ? "price-card__avail--ok" : ""}`}>
            {p.availability}
          </span>
        )}
      </div>
    </a>
  );
}

function GameDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [game, setGame] = useState<Game | null>(null);

  useEffect(() => {
    if (id) {
      getGame(Number(id)).then(setGame).catch(console.error);
    }
  }, [id]);

  if (!game) return <p className="loading">Chargement...</p>;

  const priceChartingPrices = game.prices?.filter((p) => p.source === "pricecharting") || [];
  const otherPrices = game.prices?.filter((p) => p.source !== "pricecharting") || [];

  return (
    <div>
      <Link to="/games" style={{ marginBottom: "1rem", display: "inline-block" }}>
        &larr; Retour au catalogue
      </Link>

      <div className="game-detail">
        <div>
          {game.cover_url ? (
            <img className="game-detail__cover" src={game.cover_url} alt={game.title} />
          ) : (
            <div
              className="game-detail__cover"
              style={{ height: 400, background: "var(--bg-secondary)", borderRadius: "var(--radius)" }}
            />
          )}
        </div>

        <div>
          <h1 className="game-detail__title">{game.title}</h1>
          {game.title_en && game.title_en !== game.title && (
            <p className="game-detail__title-en">{game.title_en}</p>
          )}
          <p className="game-detail__release">
            {game.release_date || "Date de sortie inconnue"}
          </p>

          {/* Prix PriceCharting */}
          {priceChartingPrices.length > 0 && (
            <div className="price-section">
              <h3 style={{ marginBottom: "0.75rem" }}>Cote Collector</h3>
              {priceChartingPrices.map((p) => (
                <PriceChartingCard key={p.id} p={p} />
              ))}
              <h4 style={{ marginTop: "1rem", marginBottom: "0.25rem", fontSize: "0.95rem" }}>
                Évolution de la cote
              </h4>
              <PriceHistoryChart gameId={game.id} />
            </div>
          )}

          {/* Autres prix (Amazon, Galaxus) */}
          {otherPrices.length > 0 && (
            <div className="price-section">
              <h3 style={{ marginBottom: "0.75rem" }}>Prix boutiques</h3>
              {otherPrices.map((p) => (
                <GenericPriceCard key={p.id} p={p} />
              ))}
            </div>
          )}

          {/* Annonces en cours (Ricardo + eBay) */}
          {game.listings && game.listings.length > 0 && (
            <div className="listings-section" style={{ marginTop: "1.5rem" }}>
              <h3 style={{ marginBottom: "0.75rem" }}>
                Annonces en cours ({game.listings.length})
              </h3>
              <table className="listings-table">
                <thead>
                  <tr>
                    <th>Annonce</th>
                    <th>Prix</th>
                    <th>Region</th>
                    <th>Etat</th>
                    <th>Encheres</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {game.listings.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <a href={l.listing_url} target="_blank" rel="noopener noreferrer">
                          {l.title.length > 50 ? l.title.slice(0, 50) + "..." : l.title}
                        </a>
                      </td>
                      <td className="listings-table__price">
                        {parseFloat(l.current_price).toFixed(2)} {l.currency}
                      </td>
                      <td>
                        {l.region && l.region !== "unknown" ? (
                          <span className={`tag tag--region tag--region-${l.region.toLowerCase()}`}>
                            {l.region}
                          </span>
                        ) : (
                          <span style={{ color: "var(--text-secondary)" }}>-</span>
                        )}
                      </td>
                      <td className="listings-table__condition">
                        {l.condition || "-"}
                      </td>
                      <td className="listings-table__bids">
                        {l.bid_count || "-"}
                      </td>
                      <td>
                        <span className={`tag tag--source tag--${l.source}`}>{l.source}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3 style={{ marginBottom: "0.5rem", marginTop: "1.5rem" }}>Plateformes</h3>
          <div className="tags" style={{ marginBottom: "1.5rem" }}>
            {game.machines.map((m) => (
              <span key={m.id} className="tag">
                {m.name}
              </span>
            ))}
          </div>

          <h3 style={{ marginBottom: "0.5rem" }}>Genres</h3>
          <div className="tags">
            {game.genres.map((g) => (
              <span key={g.id} className="tag tag--genre">
                {g.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default GameDetailPage;
