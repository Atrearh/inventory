// front/src/context/AppContext.tsx
import { ReactNode, useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom"; 
import { usePersistentState } from "../hooks/usePersistentState";
import { createCustomContext } from "../utils/createContext";
import { LoginCredentials, getMe, login as apiLogin, logout as apiLogout } from "../api/auth.api";
import { handleApiError } from "../utils/apiErrorHandler";
import { Spin, App, notification } from "antd";
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
  const navigate = useNavigate(); 

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
      console.log(`AppContext: Changing language to ${lng}`);
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
        notification.success({
          message: t("login_success", "Успішний вхід"),
          placement: "topRight",
        });
        navigate("/"); 
      } catch (error: any) {
        console.error("AppContext: Login failed:", error);
        const apiError = handleApiError(error, t);
        notification.error({
          message: apiError.message,
          placement: "topRight",
        });
        throw apiError;
      }
    },
    [t, queryClient, navigate],
  );

  const handleLogout = useCallback(
    async () => {
      try {
        await apiLogout();
        notification.success({
          message: t("logout_success", "Успішний вихід"),
          placement: "topRight",
        });
        queryClient.setQueryData(["auth", "me"], null);
        navigate("/login"); 
      } catch (error: any) {
        console.error("AppContext: Logout failed:", error);
        const apiError = handleApiError(error, t);
        notification.error({
          message: apiError.message,
          placement: "topRight",
        });
        throw apiError;
      } finally {
        queryClient.clear();
        sessionStorage.clear();
      }
    },
    [t, queryClient, navigate],
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
    <App>
      <AppProviderBase value={value}>
        <ErrorBoundary t={t}>
          <Suspense
            fallback={<Spin size="large" tip={t("loading", "Завантаження...")} />}
          >
            {children}
          </Suspense>
        </ErrorBoundary>
      </AppProviderBase>
    </App>
  );
};

export { AppContext, useAppContext, AppProvider };
