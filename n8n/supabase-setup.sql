-- Amicana RAG - esquema de Supabase (pgvector).
-- Correr una sola vez en Supabase -> SQL Editor.

create extension if not exists vector;

create table if not exists documents (
  id          bigint generated always as identity primary key,
  source      text not null,        -- 'faq' | 'curso' | 'aviso'
  external_id text not null,        -- id del FAQ/curso/aviso de origen
  content     text not null,
  embedding   vector(768),          -- dimension de text-embedding-004
  updated_at  timestamptz not null default now(),
  unique (source, external_id)
);

-- OJO con el indice vectorial: NO crear un ivfflat mientras la tabla sea chica.
-- Un ivfflat con lists=100 sobre pocas filas reparte los vectores en listas casi vacias
-- y, como ivfflat.probes vale 1 por default, la busqueda escanea UNA sola lista y
-- devuelve 1 resultado sin importar el match_count. Con menos de ~1000 filas el scan
-- secuencial es exacto y practicamente instantaneo.
--
-- Si ya lo creaste, borralo:
drop index if exists documents_embedding_idx;
--
-- Recien cuando la tabla pase de unos miles de filas, crear el indice con lists
-- proporcional (regla practica: filas/1000, minimo 1) y subir probes en la sesion:
--   create index documents_embedding_idx
--     on documents using ivfflat (embedding vector_cosine_ops) with (lists = 10);
--   set ivfflat.probes = 4;

create or replace function match_documents(
  query_embedding vector(768),
  match_count int default 4
)
returns table (source text, content text, similarity float)
language sql stable
as $$
  select source, content, 1 - (embedding <=> query_embedding) as similarity
  from documents
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- Verificacion rapida (debe devolver 0 filas antes de la ingesta):
-- select count(*) from documents;
