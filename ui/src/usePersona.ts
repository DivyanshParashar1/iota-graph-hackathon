import { useEffect, useState } from "react";

// Who the browser is "viewing as": an employee id, remembered per browser. This is a persona switch for the
// MVP, not access control - there is no auth (see ripple/api/deps.py).

const KEY = "ripple.employee";
const EVENT = "ripple:persona";

export function getPersona(): string {
  try {
    return localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setPersona(id: string) {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));
}

export function usePersona(): [string, (id: string) => void] {
  const [id, setId] = useState(getPersona);
  useEffect(() => {
    const on = (e: Event) => setId((e as CustomEvent<string>).detail ?? getPersona());
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);
  return [id, setPersona];
}
