import { Suspense } from "react";
import { ExperimentsView } from "./ExperimentsView";

export default function Page() {
  return (
    <Suspense>
      <ExperimentsView />
    </Suspense>
  );
}
