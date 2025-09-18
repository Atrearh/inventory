// front/src/hooks/usePersistentState.ts
import { useState, useEffect, Dispatch, SetStateAction } from "react";

export function usePersistentState<T>(
  key: string,
  defaultValue: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    try {
      const storedValue = localStorage.getItem(key);
      return storedValue ? JSON.parse(storedValue) as T : defaultValue; // Cast для TS
    } catch {
      // Фallback на default при помилці parse
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch {
      // Ігнор: storage full, etc. (логувати в dev)
    }
  }, [key, state]);

  return [state, setState];
};