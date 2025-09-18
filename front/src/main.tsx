import { ConfigProvider, theme } from "antd";
import React, { useEffect, useMemo } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider, QueryCache } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { useTranslation } from "react-i18next";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./components/i18n";
import "./index.css";
import { AppProvider, useAppContext } from "./context/AppContext";
import i18n from "./components/i18n"; 
import { AxiosError } from "axios";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1, // Можна поставити 0, щоб не повторювати запит при 401
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
    },
  },

  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof AxiosError && error.response?.status === 401) {
        if (window.location.pathname !== "/login") {
          queryClient.clear();
          window.location.href = "/login";
        }
      }
    },
  }),
});

const AppWithTheme: React.FC = () => {
  const { dark } = useAppContext();
  const themeObj = useMemo(
    () => ({
      algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
      token: {
        colorPrimary: "#1890ff",
        colorTextBase: dark ? "#d9d9d9" : "#333",
        colorBgBase: dark ? "#1a1a1a" : "#f5f5f5",
        colorBgContainer: dark ? "#2c2c2c" : "#fafafa",
        colorBorder: dark ? "#444444" : "#d9d9d9",
      },
    }),
    [dark],
  );

  useEffect(() => {
    document.body.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <ConfigProvider theme={themeObj}>
      <App />
    </ConfigProvider>
  );
};

const Root = () => {
  const { t } = useTranslation();
  return (
    <React.StrictMode>
      <ErrorBoundary t={t}>
        <QueryClientProvider client={queryClient}>
          <AppProvider>
            <BrowserRouter
              future={{
                v7_startTransition: true,
                v7_relativeSplatPath: true,
              }}
            >
              <AppWithTheme />
            </BrowserRouter>
          </AppProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <ErrorBoundary t={i18n.t}> 
    <Root />
  </ErrorBoundary>
);