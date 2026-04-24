import type {
  Game,
  Genre,
  Machine,
  Opportunity,
  PaginatedResponse,
  PriceHistoryPoint,
  Stats,
} from "./types";

const API_BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

export function getGames(params: Record<string, string> = {}): Promise<PaginatedResponse<Game>> {
  const query = new URLSearchParams(params).toString();
  return fetchJSON(`${API_BASE}/games/?${query}`);
}

export function getGame(id: number): Promise<Game> {
  return fetchJSON(`${API_BASE}/games/${id}/`);
}

export function getMachines(): Promise<PaginatedResponse<Machine>> {
  return fetchJSON(`${API_BASE}/machines/?page_size=100`);
}

export function getGenres(): Promise<PaginatedResponse<Genre>> {
  return fetchJSON(`${API_BASE}/genres/?page_size=100`);
}

export function getStats(): Promise<Stats> {
  return fetchJSON(`${API_BASE}/stats/`);
}

export interface TopGame {
  id: number;
  title: string;
  cover_url: string;
  machines: string[];
  loose_price: string;
  loose_price_chf: string | null;
  cib_price: string | null;
  cib_price_chf: string | null;
  new_price: string | null;
  new_price_chf: string | null;
  graded_price: string | null;
  currency: string;
  ricardo_price: string | null;
  ricardo_url: string | null;
  ricardo_bids: number | null;
}

export function getTopExpensive(platform?: string): Promise<TopGame[]> {
  const params = platform ? `?platform=${platform}` : "";
  return fetchJSON(`${API_BASE}/top/${params}`);
}

export interface AutocompleteSuggestion {
  id: number;
  title: string;
  cover_url: string;
}

export function getAutocomplete(q: string): Promise<AutocompleteSuggestion[]> {
  return fetchJSON(`${API_BASE}/autocomplete/?q=${encodeURIComponent(q)}`);
}

export function getPriceHistory(gameId: number): Promise<PriceHistoryPoint[]> {
  return fetchJSON(`${API_BASE}/games/${gameId}/price-history/`);
}

export function getOpportunities(params: Record<string, string> = {}): Promise<Opportunity[]> {
  const query = new URLSearchParams(params).toString();
  return fetchJSON(`${API_BASE}/opportunities/?${query}`);
}

export interface MarketCoteStats {
  count: number;
  avg: number;
  median: number;
  min: number;
  max: number;
  stddev: number;
}

export interface MarketCoteSale {
  final_price: string;
  currency: string;
  condition: string;
  region: string;
  platform_slug: string;
  listing_title: string;
  listing_url: string;
  source: string;
  sold_at: string;
}

export interface MarketCoteResponse {
  currency: string;
  period_days: number;
  total_sales: number;
  by_condition: Record<string, MarketCoteStats>;
  recent_sales: MarketCoteSale[];
}

export function getMarketCote(gameId: number, days = 365): Promise<MarketCoteResponse> {
  return fetchJSON(`${API_BASE}/market-cote/?game_id=${gameId}&days=${days}`);
}
