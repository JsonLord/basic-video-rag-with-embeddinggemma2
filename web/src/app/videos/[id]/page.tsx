import { Suspense } from "react";
import { VideoDetailView } from "./VideoDetailView";

export default function Page() {
  return (
    <Suspense>
      <VideoDetailView />
    </Suspense>
  );
}
