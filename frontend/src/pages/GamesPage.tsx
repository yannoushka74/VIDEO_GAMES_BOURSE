import { useEffect, useState } from "react";
import { getGames, getGenres, getMachines } from "../api";
import GameCard from "../components/GameCard";
import Pagination from "../components/Pagination";
import SearchAutocomplete from "../components/SearchAutocomplete";
import type { Game, Genre, Machine } from "../types";

const PAGE_SIZE = 50;

const ORDERINGS: { value: string; label: string }[] = [
  { value: "title", label: "Titre (A→Z)" },
  { value: "-title", label: "Titre (Z→A)" },
  { value: "-latest_loose_price", label: "Prix : élevé → bas" },
  { value: "latest_loose_price", label: "Prix : bas → élevé" },
  { value: "-release_date", label: "Sortie récente" },
  { value: "release_date", label: "Sortie ancienne" },
];

function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [machineFilter, setMachineFilter] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
  const [ordering, setOrdering] = useState("title");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [includeUnverified, setIncludeUnverified] = useState(false);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [loading, setLoading] = useState(true);

  // Charger les filtres au montage
  useEffect(() => {
    getMachines().then((data) => setMachines(data.results));
    getGenres().then((data) => setGenres(data.results));
  }, []);

  // Charger les jeux quand les filtres changent
  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page) };
    if (search) params.search = search;
    if (machineFilter) params.machine = machineFilter;
    if (genreFilter) params.genre = genreFilter;
    if (ordering) params.ordering = ordering;
    if (priceMin) params.price_min = priceMin;
    if (priceMax) params.price_max = priceMax;
    if (includeUnverified) params.include_unverified = "true";
    // Si tri par prix, exclure les jeux sans prix pour éviter les NULL en tête
    if (ordering.includes("latest_loose_price")) params.has_price = "true";

    getGames(params)
      .then((data) => {
        setGames(data.results);
        setTotalCount(data.count);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, search, machineFilter, genreFilter, ordering, priceMin, priceMax, includeUnverified]);

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const resetPriceFilter = () => {
    setPriceMin("");
    setPriceMax("");
    setPage(1);
  };

  return (
    <div>
      <h1 style={{ marginBottom: "1.5rem" }}>Catalogue</h1>

      <div className="filters">
        <SearchAutocomplete value={search} onChange={handleSearch} />
        <select
          value={machineFilter}
          onChange={(e) => {
            setMachineFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Toutes les plateformes</option>
          {machines.map((m) => (
            <option key={m.id} value={m.slug}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          value={genreFilter}
          onChange={(e) => {
            setGenreFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les genres</option>
          {genres.map((g) => (
            <option key={g.id} value={g.slug}>
              {g.name}
            </option>
          ))}
        </select>
        <select
          value={ordering}
          onChange={(e) => {
            setOrdering(e.target.value);
            setPage(1);
          }}
        >
          {ORDERINGS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <input
          type="number"
          min="0"
          step="1"
          placeholder="Prix min ($)"
          value={priceMin}
          onChange={(e) => {
            setPriceMin(e.target.value);
            setPage(1);
          }}
          style={{ width: 110 }}
        />
        <input
          type="number"
          min="0"
          step="1"
          placeholder="Prix max ($)"
          value={priceMax}
          onChange={(e) => {
            setPriceMax(e.target.value);
            setPage(1);
          }}
          style={{ width: 110 }}
        />
        {(priceMin || priceMax) && (
          <button type="button" onClick={resetPriceFilter}>
            Effacer
          </button>
        )}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            color: "var(--text-secondary)",
            fontSize: "0.85rem",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={includeUnverified}
            onChange={(e) => {
              setIncludeUnverified(e.target.checked);
              setPage(1);
            }}
          />
          Inclure les jeux non vérifiés PAL
        </label>
      </div>

      {loading ? (
        <p className="loading">Chargement...</p>
      ) : (
        <>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            {totalCount.toLocaleString("fr-FR")} jeu{totalCount > 1 ? "x" : ""} trouvé{totalCount > 1 ? "s" : ""}
          </p>
          <div className="games-grid">
            {games.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
          {games.length === 0 && (
            <p className="loading">Aucun jeu trouvé.</p>
          )}
          <Pagination
            page={page}
            totalCount={totalCount}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}

export default GamesPage;
