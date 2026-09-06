// The only file a host ever imports from — the "one entrypoint" rule. Note that
// DynamicUserManager/DynamicUserAdminManager and useDynamicUserConfig/useDynamicUserAdminConfig
// are never exported here, only hooks, both key factories, and types. There is no provider to
// export — the host mounts appkit's ApiClientProvider once and adds BOTH this app's basePath
// entries to its `basePaths` map: `dynamic_user` -> "/api/v1/users" and
// `dynamic_user_admin` -> "/api/v1/admin/users" (see README.md's "Usage" section).

// --- self-service hooks -------------------------------------------------------------------
export { useMe } from "./hooks/useMe.js";
export { useUpdateMe } from "./hooks/useUpdateMe.js";
export { useMyProfile } from "./hooks/useMyProfile.js";
export { useUpdateMyProfile } from "./hooks/useUpdateMyProfile.js";
export { useMySetting } from "./hooks/useMySetting.js";
export { useUpdateMySetting } from "./hooks/useUpdateMySetting.js";
export { usePublicProfiles } from "./hooks/usePublicProfiles.js";
export { usePublicProfile } from "./hooks/usePublicProfile.js";
export { useMyDeletionRequest } from "./hooks/useMyDeletionRequest.js";
export { useRequestDeletion } from "./hooks/useRequestDeletion.js";
export { useCancelDeletionRequest } from "./hooks/useCancelDeletionRequest.js";

// --- admin hooks ----------------------------------------------------------------------------
export { useAdminUsers } from "./hooks/useAdminUsers.js";
export { useCreateAdminUser } from "./hooks/useCreateAdminUser.js";
export { useAdminUser } from "./hooks/useAdminUser.js";
export { useUpdateAdminUser } from "./hooks/useUpdateAdminUser.js";
export { useDeleteAdminUser } from "./hooks/useDeleteAdminUser.js";
export { useSetAdminUserPassword } from "./hooks/useSetAdminUserPassword.js";
export { useAdminUserProfile } from "./hooks/useAdminUserProfile.js";
export { useUpdateAdminUserProfile } from "./hooks/useUpdateAdminUserProfile.js";
export { useAdminUserSetting } from "./hooks/useAdminUserSetting.js";
export { useUpdateAdminUserSetting } from "./hooks/useUpdateAdminUserSetting.js";
export { useAdminProfiles } from "./hooks/useAdminProfiles.js";
export { useCreateAdminProfile } from "./hooks/useCreateAdminProfile.js";
export { useAdminProfile } from "./hooks/useAdminProfile.js";
export { useUpdateAdminProfileById } from "./hooks/useUpdateAdminProfileById.js";
export { useDeleteAdminProfile } from "./hooks/useDeleteAdminProfile.js";
export { useAdminSettings } from "./hooks/useAdminSettings.js";
export { useCreateAdminSetting } from "./hooks/useCreateAdminSetting.js";
export { useAdminSetting } from "./hooks/useAdminSetting.js";
export { useUpdateAdminSettingById } from "./hooks/useUpdateAdminSettingById.js";
export { useDeleteAdminSetting } from "./hooks/useDeleteAdminSetting.js";
export { useAdminDeletionRequests } from "./hooks/useAdminDeletionRequests.js";
export { useAdminDeletionRequest } from "./hooks/useAdminDeletionRequest.js";
export { useCreateAdminDeletionRequest } from "./hooks/useCreateAdminDeletionRequest.js";
export { useCancelAdminDeletionRequest } from "./hooks/useCancelAdminDeletionRequest.js";
export { useReviewDeletionRequest } from "./hooks/useReviewDeletionRequest.js";
export { useFinalizeDeletionRequest } from "./hooks/useFinalizeDeletionRequest.js";
export { useAdminChangeLog } from "./hooks/useAdminChangeLog.js";
export { useAdminChangeLogEntry } from "./hooks/useAdminChangeLogEntry.js";
export { useDeleteAdminChangeLogEntry } from "./hooks/useDeleteAdminChangeLogEntry.js";
export { useAdminLogEntries } from "./hooks/useAdminLogEntries.js";
export { useAdminLogEntry } from "./hooks/useAdminLogEntry.js";
export { useDeleteAdminLogEntry } from "./hooks/useDeleteAdminLogEntry.js";
export { useAdminGroups } from "./hooks/useAdminGroups.js";
export { useAdminGroup } from "./hooks/useAdminGroup.js";
export { useAdminPermissions } from "./hooks/useAdminPermissions.js";

// --- key factories ----------------------------------------------------------------------------
export { dynamicUserKeys, dynamicUserAdminKeys } from "./hooks/keys.js";

// --- types ------------------------------------------------------------------------------------
export type { ReviewDeletionRequestVariables } from "./hooks/useReviewDeletionRequest.js";
export type { SetAdminUserPasswordVariables } from "./hooks/useSetAdminUserPassword.js";
export type {
  AdminChangeLogEntry,
  AdminChangeLogParams,
  AdminDeletionRequest,
  AdminDeletionRequestsParams,
  AdminGroup,
  AdminLogEntriesParams,
  AdminLogEntry,
  AdminPermission,
  AdminProfile,
  AdminProfilesParams,
  AdminSetting,
  AdminSettingsParams,
  AdminUser,
  AdminUsersParams,
  CreateAdminDeletionRequestInput,
  CreateAdminProfileInput,
  CreateAdminSettingInput,
  CreateAdminUserInput,
  DeletionRequest,
  DeletionStatus,
  HttpClient,
  MyProfile,
  MySetting,
  PaginatedAdminChangeLogEntryList,
  PaginatedAdminDeletionRequestList,
  PaginatedAdminGroupList,
  PaginatedAdminLogEntryList,
  PaginatedAdminPermissionList,
  PaginatedAdminProfileList,
  PaginatedAdminSettingList,
  PaginatedAdminUserList,
  PaginatedPublicProfileList,
  PublicProfile,
  PublicProfilesParams,
  PublicUser,
  RequestDeletionInput,
  ReviewDeletionInput,
  SetAdminUserPasswordInput,
  UpdateAdminProfileInput,
  UpdateAdminSettingInput,
  UpdateAdminUserInput,
  UpdateMeInput,
  UpdateMyProfileInput,
  UpdateMySettingInput,
  User,
} from "./types.js";
