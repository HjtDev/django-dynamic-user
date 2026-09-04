"use client";

import { usePublicProfile } from "@hjtdev/django-dynamic-user";

// `id` here is the TARGET USER's id, not the Profile row's own pk — docs/CONTRACT.md §5's own
// note on PublicProfileDetailView's lookup_field="user_id".
export function ProfileDetailClient({ id }: { id: string }) {
  const query = usePublicProfile(Number(id));

  if (query.isLoading) return <p>Loading…</p>;
  if (query.isError) {
    // A private profile requested by a stranger 404s here — same response shape as "doesn't
    // exist", by design (docs/CONTRACT.md §5's existence-leak guard).
    return <p style={{ color: "crimson" }}>{query.error.message}</p>;
  }

  const profile = query.data!;
  return (
    <section>
      <h2>{profile.user.username}</h2>
      <p>{profile.bio || "(no bio)"}</p>
      <p>
        <a href="/profiles">← back to public profiles</a>
      </p>
    </section>
  );
}
