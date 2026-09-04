"use client";

import { useState, useEffect } from "react";
import {
  useMe,
  useMyProfile,
  useUpdateMyProfile,
  useMySetting,
  useUpdateMySetting,
  type MyProfile,
  type MySetting,
  type UpdateMyProfileInput,
  type UpdateMySettingInput,
} from "@hjtdev/django-dynamic-user";

// The SDK's generated types (frontend/src/schema.d.ts) are pinned to the PACKAGE's own default
// schema — they know nothing about `tagline`/`theme`/`department`, core's own extra fields on
// THIS host. That's expected, not a bug: the schema is generated once from the package's own
// OpenAPI spec, not per-host. The wire round trip (what Phase 8 actually verifies) needs no SDK
// change at all; a TypeScript consumer widens the type locally, same as any other API client
// consuming a field its generated types don't know about.
type SubclassedProfile = MyProfile & { tagline: string };
type SubclassedSetting = MySetting & { theme: string };

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

  const subclassedProfile = profile.data as SubclassedProfile | undefined;
  const subclassedSetting = setting.data as SubclassedSetting | undefined;

  return (
    <div style={{ display: "grid", gap: "2rem" }}>
      <section>
        <h2>
          USER_READ_FIELDS (GET /me/ — includes core.User&apos;s own extra `department` field,
          entirely read-only: no self-service /me/ PATCH exists)
        </h2>
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

      {subclassedProfile && (
        <ProfileForm
          bio={subclassedProfile.bio}
          isPublic={subclassedProfile.is_public}
          tagline={subclassedProfile.tagline}
        />
      )}
      {subclassedSetting && (
        <SettingForm
          language={subclassedSetting.language}
          timezone={subclassedSetting.timezone}
          notificationsEnabled={subclassedSetting.notifications_enabled}
          theme={subclassedSetting.theme}
        />
      )}
    </div>
  );
}

function ProfileForm({
  bio,
  isPublic,
  tagline,
}: {
  bio: string;
  isPublic: boolean;
  tagline: string;
}) {
  const update = useUpdateMyProfile();
  const [form, setForm] = useState({ bio, is_public: isPublic, tagline });
  useEffect(() => setForm({ bio, is_public: isPublic, tagline }), [bio, isPublic, tagline]);

  return (
    <section>
      <h2>
        PROFILE_EDITABLE_FIELDS (PATCH /me/profile/) — <code>tagline</code> is this host&apos;s own
        extra field, the one this playground&apos;s headline check round-trips
      </h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(form as UpdateMyProfileInput & { tagline: string });
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
          tagline (core.Profile&apos;s own field)
          <input
            value={form.tagline}
            onChange={(e) => setForm({ ...form, tagline: e.target.value })}
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
  theme,
}: {
  language: string;
  timezone: string;
  notificationsEnabled: boolean;
  theme: string;
}) {
  const update = useUpdateMySetting();
  const [form, setForm] = useState({
    language,
    timezone,
    notifications_enabled: notificationsEnabled,
    theme,
  });
  useEffect(
    () =>
      setForm({ language, timezone, notifications_enabled: notificationsEnabled, theme }),
    [language, timezone, notificationsEnabled, theme]
  );

  return (
    <section>
      <h2>SETTING_EDITABLE_FIELDS (PATCH /me/setting/) — includes core.Setting&apos;s own `theme`</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(form as UpdateMySettingInput & { theme: string });
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
          theme (core.Setting&apos;s own field)
          <input value={form.theme} onChange={(e) => setForm({ ...form, theme: e.target.value })} />
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
