import { Suspense } from "react";
import { SearchView } from "./SearchView";

export default function Page() {
  return (
    <Suspense>
      <SearchView />
    </Suspense>
  );
}
