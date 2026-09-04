"use client";

import { useState } from "react";
import {
  useMyDeletionRequest,
  useRequestDeletion,
  useCancelDeletionRequest,
} from "@hjtdev/django-dynamic-user";

export function DeletionClient() {
  const query = useMyDeletionRequest();
  const request = useRequestDeletion();
  const cancel = useCancelDeletionRequest();
  const [reason, setReason] = useState("");

  return (
    <section>
      <h2>Account deletion</h2>

      {query.isLoading && <p>Checking for an existing request…</p>}

      {query.isError && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate({ reason });
          }}
          style={{ display: "grid", gap: "0.5rem", maxWidth: "24rem" }}
        >
          <p>You have no active deletion request.</p>
          <label>
            reason (optional)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
          </label>
          <button type="submit" disabled={request.isPending}>
            Request account deletion
          </button>
          {request.isError && <span style={{ color: "crimson" }}>{request.error.message}</span>}
        </form>
      )}

      {query.isSuccess && (
        <div>
          <p>
            status: <strong>{query.data.status}</strong>
            <br />
            requested_at: {query.data.requested_at}
            <br />
            finalize_at: {query.data.finalize_at ?? "—"}
          </p>
          {query.data.status === "pending" && (
            <button onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              Cancel request
            </button>
          )}
          {cancel.isError && <p style={{ color: "crimson" }}>{cancel.error.message}</p>}
        </div>
      )}
    </section>
  );
}
