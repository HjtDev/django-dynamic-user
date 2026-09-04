"use client";

import { useState, useEffect } from "react";
import {
  useMe,
  useMyProfile,
  useUpdateMyProfile,
  useMySetting,
  useUpdateMySetting,
} from "@hjtdev/django-dynamic-user";

export function MeClient() {
  const me = useMe();
  const profile = useMyProfile();
  const setting = useMySetting();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError) {
    return (
      <p>
        Not signed in. <a href="/accounts/login/?next=/">Sign in</a> to see your account.
      </p>
    );
  }

  return (
    <div style={{ display: "grid", gap: "2rem" }}>
      <section>
        <h2>USER_READ_FIELDS (GET /me/ — entirely read-only, no self-service /me/ PATCH exists)</h2>
        <table>
          <tbody>
            {Object.entries(me.data ?? {}).map(([key, value]) => (
              <tr key={key}>
                <td style={{ paddingRight: "1rem", fontFamily: "monospace" }}>{key}</td>
                <td>
                  <input value={String(value)} disabled style={{ width: "20rem" }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {profile.isSuccess && <ProfileForm bio={profile.data.bio} isPublic={profile.data.is_public} />}
      {setting.isSuccess && (
        <SettingForm
          language={setting.data.language}
          timezone={setting.data.timezone}
          notificationsEnabled={setting.data.notifications_enabled}
        />
      )}
    </div>
  );
}

function ProfileForm({ bio, isPublic }: { bio: string; isPublic: boolean }) {
  const update = useUpdateMyProfile();
  const [form, setForm] = useState({ bio, is_public: isPublic });
  useEffect(() => setForm({ bio, is_public: isPublic }), [bio, isPublic]);

  return (
    <section>
      <h2>PROFILE_EDITABLE_FIELDS (PATCH /me/profile/)</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(form);
        }}
        style={{ display: "grid", gap: "0.5rem", maxWidth: "24rem" }}
      >
        <label>
          bio
          <textarea
            value={form.bio}
            onChange={(e) => setForm({ ...form, bio: e.target.value })}
            rows={3}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => setForm({ ...form, is_public: e.target.checked })}
          />{" "}
          is_public
        </label>
        <button type="submit" disabled={update.isPending}>
          Save profile
        </button>
        {update.isSuccess && <span style={{ color: "green" }}>Saved.</span>}
        {update.isError && <span style={{ color: "crimson" }}>{update.error.message}</span>}
      </form>
    </section>
  );
}

function SettingForm({
  language,
  timezone,
  notificationsEnabled,
}: {
  language: string;
  timezone: string;
  notificationsEnabled: boolean;
}) {
  const update = useUpdateMySetting();
  const [form, setForm] = useState({
    language,
    timezone,
    notifications_enabled: notificationsEnabled,
  });
  useEffect(
    () => setForm({ language, timezone, notifications_enabled: notificationsEnabled }),
    [language, timezone, notificationsEnabled]
  );

  return (
    <section>
      <h2>SETTING_EDITABLE_FIELDS (PATCH /me/setting/)</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(form);
        }}
        style={{ display: "grid", gap: "0.5rem", maxWidth: "24rem" }}
      >
        <label>
          language
          <input
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
          />
        </label>
        <label>
          timezone
          <input
            value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.notifications_enabled}
            onChange={(e) => setForm({ ...form, notifications_enabled: e.target.checked })}
          />{" "}
          notifications_enabled
        </label>
        <button type="submit" disabled={update.isPending}>
          Save setting
        </button>
        {update.isSuccess && <span style={{ color: "green" }}>Saved.</span>}
        {update.isError && <span style={{ color: "crimson" }}>{update.error.message}</span>}
      </form>
    </section>
  );
}
