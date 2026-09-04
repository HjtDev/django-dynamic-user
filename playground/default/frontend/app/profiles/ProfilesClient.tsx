"use client";

import { useState } from "react";
import { usePublicProfiles } from "@hjtdev/django-dynamic-user";

const PAGE_SIZE = 10;

export function ProfilesClient() {
  const [page, setPage] = useState(1);
  const query = usePublicProfiles({ page, page_size: PAGE_SIZE });

  if (query.isLoading) return <p>Loading…</p>;
  if (query.isError) return <p style={{ color: "crimson" }}>{query.error.message}</p>;

  const data = query.data!;

  return (
    <section>
      <h2>Public profiles (is_public=true only — bob's own is never here)</h2>
      <p>
        {data.count} total — page {page}
      </p>
      <ul>
        {data.results.map((p) => (
          <li key={p.id}>
            <a href={`/profiles/${p.user.id}`}>{p.user.username}</a> — {p.bio || "(no bio)"}
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button disabled={!data.previous} onClick={() => setPage((p) => p - 1)}>
          ← prev
        </button>
        <button disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
          next →
        </button>
      </div>
    </section>
  );
}
