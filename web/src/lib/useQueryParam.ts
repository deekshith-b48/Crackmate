"use client";
import { useEffect, useState } from "react";

/** Reads ?name=value once on the client. Static export has no server-side search params. */
export function useQueryParam(name: string) {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => { setValue(new URLSearchParams(window.location.search).get(name)); }, [name]);
  return value;
}
