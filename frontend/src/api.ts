import type { Game, Genre, Machine, PaginatedResponse, Stats } from "./types";

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
  cib_price: string | null;
  new_price: string | null;
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
