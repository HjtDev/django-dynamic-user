"use client";

import { isApiError } from "@hjtdev/appkit";
import {
  useAdminDeletionRequests,
  useReviewDeletionRequest,
  useFinalizeDeletionRequest,
} from "@hjtdev/django-dynamic-user";

// See ../AdminPanelClient.tsx's own comment — react-query types a hook's error as the generic
// `Error`; narrow to appkit's own ApiError (which carries `.status`) with its type guard.
function apiStatus(error: unknown): number | string {
  return isApiError(error) ? error.status : "?";
}

export function AdminDeletionsClient() {
  const list = useAdminDeletionRequests();
  const review = useReviewDeletionRequest();
  const finalize = useFinalizeDeletionRequest();

  if (list.isLoading) return <p>Loading…</p>;
  if (list.isError) {
    return (
      <p style={{ color: "crimson" }}>
        {list.error.message} (status {apiStatus(list.error)})
      </p>
    );
  }

  return (
    <section>
      <h2>Admin — deletion requests</h2>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th align="left">id</th>
            <th align="left">user</th>
            <th align="left">status</th>
            <th align="left">finalize_at</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {list.data!.results.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.user}</td>
              <td>{r.status}</td>
              <td>{r.finalize_at ?? "—"}</td>
              <td style={{ display: "flex", gap: "0.5rem" }}>
                {r.status === "pending" && (
                  <>
                    <button onClick={() => review.mutate({ id: r.id, approved: true })}>
                      approve
                    </button>
                    <button onClick={() => review.mutate({ id: r.id, approved: false })}>
                      reject
                    </button>
                  </>
                )}
                {r.status === "approved" && (
                  <button onClick={() => finalize.mutate(r.id)}>
                    finalize now (bypasses grace period — superuser only)
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {review.isError && (
        <p style={{ color: "crimson" }}>
          review: {review.error.message} (status {apiStatus(review.error)})
        </p>
      )}
      {finalize.isError && (
        <p style={{ color: "crimson" }}>
          finalize: {finalize.error.message} (status {apiStatus(finalize.error)})
        </p>
      )}
    </section>
  );
}
