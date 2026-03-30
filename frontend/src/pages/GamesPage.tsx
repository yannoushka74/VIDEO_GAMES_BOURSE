import { useEffect, useState } from "react";
import { getGames, getGenres, getMachines } from "../api";
import GameCard from "../components/GameCard";
import Pagination from "../components/Pagination";
import SearchAutocomplete from "../components/SearchAutocomplete";
import type { Game, Genre, Machine } from "../types";

const PAGE_SIZE = 50;

function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [machineFilter, setMachineFilter] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
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

    getGames(params)
      .then((data) => {
        setGames(data.results);
        setTotalCount(data.count);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, search, machineFilter, genreFilter]);

  // Reset page quand on change de filtre
  const handleSearch = (value: string) => {
    setSearch(value);
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
            <option key={m.id} value={m.jvc_id}>
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
            <option key={g.id} value={g.jvc_id}>
              {g.name}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="loading">Chargement...</p>
      ) : (
        <>
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
