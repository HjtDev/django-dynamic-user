export const dynamic = "force-dynamic";

import { ProfileDetailClient } from "./ProfileDetailClient";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProfileDetailClient id={id} />;
}
