import { useNavigate } from "react-router-dom";
import type { Game } from "../types";
import PriceChartingIcon from "./PriceChartingIcon";

interface Props {
  game: Game;
}

function GameCard({ game }: Props) {
  const navigate = useNavigate();

  const lp = game.latest_price;
  return (
    <div className="game-card" onClick={() => navigate(`/games/${game.id}`)}>
      {game.cover_url ? (
        <img
          className="game-card__cover"
          src={game.cover_url}
          alt={game.title}
          loading="lazy"
        />
      ) : (
        <div className="game-card__cover" />
      )}
      <div className="game-card__info">
        <div className="game-card__title">{game.title}</div>
        <div className="game-card__meta">{game.release_date || "Date inconnue"}</div>

        {lp && (
          <div className="price-badge">
            <PriceChartingIcon size={14} />
            <span className="price-badge__value">
              {lp.currency === "USD" ? "$" : ""}{parseFloat(lp.price).toFixed(2)}{lp.currency !== "USD" ? ` ${lp.currency}` : ""}
            </span>
          </div>
        )}

        <div className="tags">
          {game.machines.slice(0, 3).map((m) => (
            <span key={m.id} className="tag">
              {m.name}
            </span>
          ))}
          {game.genres.slice(0, 2).map((g) => (
            <span key={g.id} className="tag tag--genre">
              {g.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default GameCard;
