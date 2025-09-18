// src/hooks/usePersistentTheme.ts
import { useSyncExternalStore, useCallback } from "react";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): boolean {
  try {
    const storedValue = localStorage.getItem("theme");
    return storedValue ? JSON.parse(storedValue) : false;
  } catch {
    return false;
  }
}

export function usePersistentTheme(): [boolean, () => void] {
  const isDark = useSyncExternalStore(subscribe, getSnapshot, () => false);

  const toggleTheme = useCallback(() => {
    const newTheme = !getSnapshot();
    localStorage.setItem("theme", JSON.stringify(newTheme));
    // Диспетчеризуємо подію, щоб інші вкладки оновили тему
    window.dispatchEvent(new StorageEvent("storage", { key: "theme" }));
  }, []);

  return [isDark, toggleTheme];
}