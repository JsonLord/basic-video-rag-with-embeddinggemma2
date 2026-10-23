import { AccessToken } from "@/components/AccessToken";
import { MentorConversation } from "@/components/MentorConversation";
export default function MentorPage() {
  return (
    <>
      <h1 className="text-3xl">Mentor</h1>
      <AccessToken />
      <MentorConversation />
    </>
  );
}
