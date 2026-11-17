-- Paste into your PRIVATE Supabase project's SQL Editor and run once.
-- RLS enabled with NO public policies. Server-only service role access.
create table if not exists public.tracked_products (
  product_id text primary key,
  game text not null,
  catalog_id text not null,
  name text not null,
  set_name text not null,
  card_number text not null,
  printing text not null default '',
  created_at timestamptz not null default now()
);
create table if not exists public.price_history (
  product_id text not null references public.tracked_products(product_id) on delete cascade,
  day date not null,
  finish text not null,
  source text not null,
  currency text not null,
  price numeric(12,4) not null check (price > 0),
  primary key(product_id,day,finish,source)
);
create index if not exists price_history_day_idx on public.price_history(day);
alter table public.tracked_products enable row level security;
alter table public.price_history enable row level security;
revoke all on public.tracked_products from anon, authenticated;
revoke all on public.price_history from anon, authenticated;
