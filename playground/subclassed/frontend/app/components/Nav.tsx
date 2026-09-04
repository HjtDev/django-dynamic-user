"use client";

import { useMe } from "@hjtdev/django-dynamic-user";
import { useState, useEffect } from "react";

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

function LogoutForm() {
  const [csrfToken, setCsrfToken] = useState("");
  useEffect(() => setCsrfToken(readCookie("csrftoken")), []);
  return (
    <form method="post" action="/accounts/logout/" style={{ display: "inline" }}>
      <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
      <button type="submit" style={{ font: "inherit" }}>
        sign out
      </button>
    </form>
  );
}

export function Nav() {
  const me = useMe();

  return (
    <nav style={{ marginBottom: "1.5rem", borderBottom: "1px solid #ccc", paddingBottom: "1rem" }}>
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        <a href="/">Me</a>
        <a href="/profiles">Public profiles</a>
        <a href="/deletion">Delete my account</a>
        <a href="/admin-panel">Admin panel</a>
        <a href="/admin-panel/deletions">Admin: deletion requests</a>
        <a href="/admin/">Jazzmin admin</a>
      </div>
      <div style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: "#555" }}>
        {me.isLoading && "checking session…"}
        {me.isError && (
          <span>
            Not signed in — <a href="/accounts/login/?next=/">sign in</a>
          </span>
        )}
        {me.isSuccess && (
          <span>
            Signed in as <strong>{me.data.username}</strong> — <LogoutForm />
          </span>
        )}
      </div>
    </nav>
  );
}
