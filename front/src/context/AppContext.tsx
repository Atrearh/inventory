import { ReactNode, useState, useEffect, useMemo, useCallback,Suspense } from "react";
import { useTranslation } from "react-i18next";
import { usePersistentState } from "../hooks/usePersistentState";
import { createCustomContext } from "../utils/createContext";
import { LoginCredentials, getMe, login as apiLogin, logout as apiLogout } from "../api/auth.api";
import { handleApiError } from "../utils/apiErrorHandler";
import { message, Spin } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { I18N_KEYS } from "../utils/i18nKeys"; 
import { UserRead } from "../types/schemas";  

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
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

// Створюємо контекст і хук
const [AppContext, AppProviderBase, useAppContext] = createCustomContext<AppContextType>()({
  name: "App",
});

// Єдиний провайдер
export const AppProvider = ({ children }: { children: ReactNode }) => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();

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

  const { data: queryUser, isLoading } = useQuery<UserRead | null, Error>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await getMe();
      } catch {
        return null;
      }
    },
    initialData: null, // Фікс TS-2345: уникаємо undefined
    enabled: true,
    staleTime: 5 * 60 * 1000, // 5 хв кеш
    retry: 0, // Не retry auth
  });

  const isAuthenticated = !!queryUser;

  useEffect(() => {
    setUser(queryUser); // Фікс TS-2345: синхронізація з query
  }, [queryUser]);

  const handleLogin = async (credentials: LoginCredentials) => {
    try {
      await apiLogin(credentials);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      message.success(t(I18N_KEYS.login_success.key, I18N_KEYS.login_success.fallback));
    } catch (error) {
      const apiError = handleApiError(error, undefined, t(I18N_KEYS.error_logging_in.key, I18N_KEYS.error_logging_in.fallback));
      throw apiError;
    }
  };

  const handleLogout = useCallback(async () => {
    try {
      await apiLogout();
      message.success(t(I18N_KEYS.logout_success.key, I18N_KEYS.logout_success.fallback));
    } catch (error) {
      const apiError = handleApiError(error, undefined, t(I18N_KEYS.error_logging_out.key, I18N_KEYS.error_logging_out.fallback));
      message.error(apiError.message);
    } finally {
      queryClient.clear(); // Очистити весь кеш
      setUser(null);
      sessionStorage.clear();
    }
  }, [t, queryClient]);

  // Об'єкт з усіма значеннями для провайдера
  const value: AppContextType = useMemo(
    () => ({
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
    }),
    [
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
      handleLogin,
      handleLogout,
    ],
  );

  return (
    <AppProviderBase value={value}>
      <Suspense
        fallback={<Spin size="large" tip={t(I18N_KEYS.loading.key, I18N_KEYS.loading.fallback)} />}
      >
        {children}
      </Suspense>
    </AppProviderBase>
  );
};

// Експортуємо єдиний хук
export { useAppContext };