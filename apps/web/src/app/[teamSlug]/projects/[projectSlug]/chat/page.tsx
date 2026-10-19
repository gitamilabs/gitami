import { redirect } from "next/navigation";

export default async function LegacyChatRedirect({
  params,
}: {
  params: Promise<{ teamSlug: string; projectSlug: string }>;
}) {
  const { teamSlug, projectSlug } = await params;
  redirect(`/${teamSlug}/${projectSlug}/chat`);
}
