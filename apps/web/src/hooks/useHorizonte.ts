import { useEffect, useState } from "react";
import { getHorizontePref, setHorizontePref, type HorizontePref } from "../prefs";

export function useHorizonte(initial?: HorizontePref) {
  const [horizonte, setHorizonteState] = useState<HorizontePref>(
    () => initial ?? getHorizontePref(),
  );

  useEffect(() => {
    setHorizontePref(horizonte);
  }, [horizonte]);

  return [horizonte, setHorizonteState] as const;
}
