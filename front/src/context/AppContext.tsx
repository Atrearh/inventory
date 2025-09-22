import { ReactNode, useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { usePersistentState } from "../hooks/usePersistentState";
import { createCustomContext } from "../utils/createContext";
import { LoginCredentials, getMe, login as apiLogin, logout as apiLogout } from "../api/auth.api";
import { handleApiError } from "../utils/apiErrorHandler";
import { Spin, App  } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRead } from "../types/schemas";
import ErrorBoundary from "../components/ErrorBoundary";
import { usePersistentTheme } from "../hooks/usePersistentTheme"; 

interface AppContextType {
  dark: boolean;
  toggleTheme: () => void;
  timezone: string;
  setTimezone: (tz: string) => void;
  language: string;
  changeLanguage: (lng: string) => void;
  pageTitle: string;
  setPageTitle: (title: string) => void;
  user: UserRead | null | undefined;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

const [AppContext, AppProviderBase, useAppContext] = createCustomContext<AppContextType>()({
  name: "App",
});

const AppProvider = ({ children }: { children: ReactNode }) => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  // --- Theme ---
  const [dark, toggleTheme] = usePersistentTheme();


  // --- Timezone ---
  const [timezone, setTimezone] = useState<string>(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );

  // --- Language ---
  const [language, setLanguage] = usePersistentState<string>("language", i18n.language || "uk");
  const changeLanguage = useCallback(
    (lng: string) => {
      setLanguage(lng);
      i18n.changeLanguage(lng);
    },
    [setLanguage, i18n],
  );

  // --- Page Title ---
  const [pageTitle, setPageTitle] = useState<string>("");

  // --- Auth ---
  const { data: user, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    retry: 0,
  });

  const isAuthenticated = !!user;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  const handleLogin = useCallback(
    async (credentials: LoginCredentials) => {
      try {
        const loggedInUser: UserRead = await apiLogin(credentials);
        queryClient.setQueryData(["auth", "me"], loggedInUser);
        message.success(t("login_success"));
      } catch (error) {
        const apiError = handleApiError(error, undefined, t("error_logging_in"));
        throw apiError;
      }
    },
    [t, queryClient, message],
  );

  const handleLogout = useCallback(
    async () => {
      try {
        await apiLogout();
        message.success(t("logout_success"));
      } catch (error) {
        const apiError = handleApiError(error, undefined, t("error_logging_out"));
        message.error(apiError.message);
      } finally {
        queryClient.clear();
        sessionStorage.clear();
      }
    },
    [t, queryClient, message],
  );

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
      language,
      changeLanguage,
      pageTitle,
      user,
      isAuthenticated,
      isLoading,
      handleLogin,
      handleLogout,
    ],
  );

  return (
    <AppProviderBase value={value}>
      <ErrorBoundary t={t}>
        <Suspense
          fallback={<Spin size="large" tip={t("loading")} />}
        >
          {children}
        </Suspense>
      </ErrorBoundary>
    </AppProviderBase>
  );
};

export { AppContext, useAppContext, AppProvider }; // Єдиний експорт