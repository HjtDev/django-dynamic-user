"use client";

import { useState, useEffect } from "react";
import { isApiError } from "@hjtdev/appkit";
import {
  useAdminUsers,
  useAdminUser,
  useUpdateAdminUser,
  useAdminUserProfile,
  useUpdateAdminUserProfile,
  useAdminUserSetting,
  useUpdateAdminUserSetting,
} from "@hjtdev/django-dynamic-user";

const PAGE_SIZE = 10;

// react-query types a hook's error as the generic `Error`; appkit's own ApiError is a subclass
// carrying `.status` — narrow with appkit's own type guard rather than casting blindly.
function apiStatus(error: unknown): number | string {
  return isApiError(error) ? error.status : "?";
}

export function AdminPanelClient() {
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const list = useAdminUsers({ page, page_size: PAGE_SIZE });

  if (list.isLoading) return <p>Loading…</p>;
  if (list.isError) {
    // ADMIN_REQUIRES_SUPERUSER's real effect lands here: a staff-but-not-superuser login gets a
    // 403 envelope from the API — the whole page fails to load, not just a hidden control.
    return (
      <p style={{ color: "crimson" }}>
        {list.error.message} (status {apiStatus(list.error)})
      </p>
    );
  }

  const data = list.data!;

  return (
    <section>
      <h2>Admin — users ({data.count} total)</h2>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th align="left">id</th>
            <th align="left">username</th>
            <th align="left">is_staff</th>
            <th align="left">is_superuser</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.username}</td>
              <td>{String(u.is_staff)}</td>
              <td>{String(u.is_superuser)}</td>
              <td>
                <button onClick={() => setSelectedId(u.id)}>manage</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
        <button disabled={!data.previous} onClick={() => setPage((p) => p - 1)}>
          ← prev
        </button>
        <button disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
          next →
        </button>
      </div>

      {selectedId !== null && <UserDetail id={selectedId} onClose={() => setSelectedId(null)} />}
    </section>
  );
}

function UserDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const user = useAdminUser(id);
  const updateUser = useUpdateAdminUser(id);
  const profile = useAdminUserProfile(id);
  const updateProfile = useUpdateAdminUserProfile(id);
  const setting = useAdminUserSetting(id);
  const updateSetting = useUpdateAdminUserSetting(id);

  const [isStaff, setIsStaff] = useState(false);
  useEffect(() => {
    if (user.data) setIsStaff(Boolean(user.data.is_staff));
  }, [user.data]);

  const [profileForm, setProfileForm] = useState({ bio: "", is_public: true });
  useEffect(() => {
    if (profile.data) setProfileForm({ bio: profile.data.bio ?? "", is_public: profile.data.is_public ?? true });
  }, [profile.data]);

  const [settingForm, setSettingForm] = useState({ language: "en", timezone: "UTC" });
  useEffect(() => {
    if (setting.data)
      setSettingForm({ language: setting.data.language ?? "en", timezone: setting.data.timezone ?? "UTC" });
  }, [setting.data]);

  return (
    <div style={{ border: "1px solid #ccc", padding: "1rem", marginTop: "1rem" }}>
      <button onClick={onClose} style={{ float: "right" }}>
        ✕
      </button>
      <h3>User #{id}</h3>

      {user.isSuccess && (
        <div>
          <label>
            is_staff — CanEscalatePrivilege gates this: a staff-but-not-superuser submit here
            must fail with 403, whole request rejected.
            <input type="checkbox" checked={isStaff} onChange={(e) => setIsStaff(e.target.checked)} />
          </label>
          <button onClick={() => updateUser.mutate({ is_staff: isStaff })} disabled={updateUser.isPending}>
            Save is_staff
          </button>
          {updateUser.isSuccess && <span style={{ color: "green" }}> Saved.</span>}
          {updateUser.isError && (
            <p style={{ color: "crimson" }}>
              {updateUser.error.message} (status {apiStatus(updateUser.error)})
            </p>
          )}
        </div>
      )}

      {profile.isSuccess && (
        <div style={{ marginTop: "1rem" }}>
          <h4>Profile (full fields — admin surface, not PROFILE_EDITABLE_FIELDS)</h4>
          <textarea
            value={profileForm.bio}
            onChange={(e) => setProfileForm({ ...profileForm, bio: e.target.value })}
          />
          <label>
            <input
              type="checkbox"
              checked={profileForm.is_public}
              onChange={(e) => setProfileForm({ ...profileForm, is_public: e.target.checked })}
            />{" "}
            is_public
          </label>
          <button onClick={() => updateProfile.mutate(profileForm)} disabled={updateProfile.isPending}>
            Save profile
          </button>
        </div>
      )}

      {setting.isSuccess && (
        <div style={{ marginTop: "1rem" }}>
          <h4>Setting</h4>
          <input
            value={settingForm.language}
            onChange={(e) => setSettingForm({ ...settingForm, language: e.target.value })}
          />
          <input
            value={settingForm.timezone}
            onChange={(e) => setSettingForm({ ...settingForm, timezone: e.target.value })}
          />
          <button onClick={() => updateSetting.mutate(settingForm)} disabled={updateSetting.isPending}>
            Save setting
          </button>
        </div>
      )}
    </div>
  );
}
