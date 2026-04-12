export interface Machine {
  id: number;
  jvc_id: number;
  name: string;
  slug: string;
}

export interface Genre {
  id: number;
  jvc_id: number;
  name: string;
  slug: string;
}

export interface Price {
  id: number;
  source: string;
  price: string;
  old_price: string | null;
  discount_percent: number | null;
  currency: string;
  cib_price: string | null;
  new_price: string | null;
  graded_price: string | null;
  box_only_price: string | null;
  manual_only_price: string | null;
  price_chf: string | null;
  cib_price_chf: string | null;
  new_price_chf: string | null;
  graded_price_chf: string | null;
  product_url: string;
  product_title: string;
  asin: string;
  image_url: string;
  rating: string | null;
  review_count: number | null;
  availability: string;
  category: string;
  scraped_at: string;
}

export interface LatestPrice {
  price: string;
  currency: string;
  source: string;
}

export interface Listing {
  id: number;
  source: string;
  platform_slug: string;
  title: string;
  listing_url: string;
  image_url: string;
  current_price: string;
  buy_now_price: string | null;
  currency: string;
  bid_count: number;
  ends_at: string | null;
  condition: string;
  region: string;
  scraped_at: string;
}

export interface Game {
  id: number;
  jvc_id: number;
  title: string;
  title_en?: string;
  game_type: number;
  release_date: string;
  cover_url: string;
  machines: Machine[];
  genres: Genre[];
  latest_price?: LatestPrice | null;
  latest_loose_price?: string | null;
  listing_count?: number;
  prices?: Price[];
  listings?: Listing[];
}

export interface PriceHistoryPoint {
  id: number;
  source: string;
  price: string;
  cib_price: string | null;
  new_price: string | null;
  graded_price: string | null;
  currency: string;
  scraped_at: string;
}

export interface Opportunity {
  listing_id: number;
  game_id: number;
  title: string;
  cover_url: string;
  machines: string[];
  platform_slug: string;
  listing_title: string;
  listing_url: string;
  listing_image: string;
  listing_price_chf: number;
  listing_price_eur: number;
  listing_price_usd: number;
  listing_currency: string;
  listing_condition: string;
  listing_source: string;
  bid_count: number;
  ends_at: string | null;
  ref_source: "cib" | "loose" | "new" | "graded";
  ref_price_usd: number;
  discount_percent: number;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Stats {
  games_count: number;
  games_count_total?: number;
  machines_count: number;
  genres_count: number;
}
