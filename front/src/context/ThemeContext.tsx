import React, { createContext, useState, useEffect, ReactNode } from "react";

// Інтерфейс для контексту теми
interface ThemeContextType {
  dark: boolean;
  setDark: (dark: boolean) => void;
}

// Створення контексту
export const ThemeContext = createContext<ThemeContextType>({
  dark: false,
  setDark: () => {},
});

// Провайдер для контексту теми
export const ThemeProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [dark, setDark] = useState(() => {
    // Завантажуємо тему з localStorage, за замовчуванням світла (false)
    return localStorage.getItem("theme") === "dark";
  });

  // Зберігаємо вибір теми в localStorage
  useEffect(() => {
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <ThemeContext.Provider value={{ dark, setDark }}>
      {children}
    </ThemeContext.Provider>
  );
};
