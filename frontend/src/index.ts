// The only file a host ever imports from — the "one entrypoint" rule. Note that
// DynamicUserManager/DynamicUserAdminManager and useDynamicUserConfig/useDynamicUserAdminConfig
// are never exported here, only hooks, both key factories, and types. There is no provider to
// export — the host mounts appkit's ApiClientProvider once and adds BOTH this app's basePath
// entries to its `basePaths` map: `dynamic_user` -> "/api/v1/users" and
// `dynamic_user_admin` -> "/api/v1/admin/users" (see README.md's "Usage" section).

// --- self-service hooks -------------------------------------------------------------------
export { useMe } from "./hooks/useMe.js";
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
export { useAdminUser } from "./hooks/useAdminUser.js";
export { useUpdateAdminUser } from "./hooks/useUpdateAdminUser.js";
export { useAdminUserProfile } from "./hooks/useAdminUserProfile.js";
export { useUpdateAdminUserProfile } from "./hooks/useUpdateAdminUserProfile.js";
export { useAdminUserSetting } from "./hooks/useAdminUserSetting.js";
export { useUpdateAdminUserSetting } from "./hooks/useUpdateAdminUserSetting.js";
export { useAdminDeletionRequests } from "./hooks/useAdminDeletionRequests.js";
export { useReviewDeletionRequest } from "./hooks/useReviewDeletionRequest.js";
export { useFinalizeDeletionRequest } from "./hooks/useFinalizeDeletionRequest.js";

// --- key factories ----------------------------------------------------------------------------
export { dynamicUserKeys, dynamicUserAdminKeys } from "./hooks/keys.js";

// --- types ------------------------------------------------------------------------------------
export type { ReviewDeletionRequestVariables } from "./hooks/useReviewDeletionRequest.js";
export type {
  AdminDeletionRequest,
  AdminDeletionRequestsParams,
  AdminProfile,
  AdminSetting,
  AdminUser,
  AdminUsersParams,
  DeletionRequest,
  DeletionStatus,
  HttpClient,
  MyProfile,
  MySetting,
  PaginatedAdminDeletionRequestList,
  PaginatedAdminUserList,
  PaginatedPublicProfileList,
  PublicProfile,
  PublicProfilesParams,
  PublicUser,
  RequestDeletionInput,
  ReviewDeletionInput,
  UpdateAdminProfileInput,
  UpdateAdminSettingInput,
  UpdateAdminUserInput,
  UpdateMyProfileInput,
  UpdateMySettingInput,
  User,
} from "./types.js";
