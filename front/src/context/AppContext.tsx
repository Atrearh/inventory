import { ReactNode, useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { usePersistentState } from "../hooks/usePersistentState";
import { createCustomContext } from "../utils/createContext";
import { UserRead } from "../types/schemas";
import { getMe, login as apiLogin, logout as apiLogout } from "../api/auth.api";
import { handleApiError } from "../utils/apiErrorHandler";
import { message } from "antd";

// Інтерфейс для всіх значень контексту
interface AppContextType {
  dark: boolean;
  toggleTheme: () => void;
  timezone: string;
  setTimezone: (tz: string) => void;
  language: string;
  changeLanguage: (lng: string) => void;
  pageTitle: string;
  setPageTitle: (title: string) => void;
  user: UserRead | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

// Створюємо контекст і хук
const [AppContext, AppProviderBase, useAppContext] = createCustomContext<AppContextType>()({
  name: "App",
});

// Єдиний провайдер
export const AppProvider = ({ children }: { children: ReactNode }) => {
  const { t, i18n } = useTranslation();

  // --- Theme ---
  const [dark, setDark] = usePersistentState<boolean>("theme", false);
  const toggleTheme = () => setDark(!dark);

  // --- Timezone ---
  const [timezone, setTimezone] = useState<string>(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );

  // --- Language ---
  const [language, setLanguage] = usePersistentState<string>(
    "language",
    i18n.language || "uk",
  );
  const changeLanguage = (lng: string) => {
    setLanguage(lng);
    i18n.changeLanguage(lng);
  };

  // --- PageTitle ---
  const [pageTitle, setPageTitle] = useState("");

  // --- Auth ---
  const [user, setUser] = useState<UserRead | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    try {
      const currentUser = await getMe();
      setUser(currentUser);
      setIsAuthenticated(true);
    } catch (error) {
      const apiError = handleApiError(error, t("error_checking_auth", "Помилка перевірки автентифікації"));
      message.error(apiError.message);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLogin = async (email: string, password: string) => {
    try {
      await apiLogin({ email, password });
      await checkAuth();
      message.success(t("login_success", "Успішний вхід!"));
    } catch (error) {
      const apiError = handleApiError(error, t("error_logging_in", "Помилка входу"));
      throw apiError;
    }
  };

  const handleLogout = useCallback(async () => {
    try {
      await apiLogout();
      message.success(t("logout_success", "У Uспішний вихід!"));
    } catch (error) {
      const apiError = handleApiError(error, t("error_logging_out", "Помилка виходу"));
      message.error(apiError.message);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      sessionStorage.clear();
    }
  }, [t]);

  // Об'єкт з усіма значеннями для провайдера
  const value: AppContextType = {
    dark,
    toggleTheme,
    timezone,
    setTimezone,
    language,
    changeLanguage,
    pageTitle,
    setPageTitle,
    user,
    isAuthenticated,
    isLoading,
    login: handleLogin,
    logout: handleLogout,
  };

  return <AppProviderBase value={value}>{children}</AppProviderBase>;
};

// Експортуємо єдиний хук
export { useAppContext };