import { Suspense } from "react";
import { ArchitectureView } from "./ArchitectureView";

export default function Page() {
  return (
    <Suspense>
      <ArchitectureView />
    </Suspense>
  );
}
