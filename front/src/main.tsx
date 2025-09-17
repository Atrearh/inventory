import { ConfigProvider, theme } from "antd";
import React, { useContext, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./context/AuthContext";
import { TimezoneProvider } from "./context/TimezoneContext";
import { ThemeContext, ThemeProvider } from "./context/ThemeContext";
import { PageTitleProvider } from "./context/PageTitleContext";
import "./components/i18n";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 хвилин
      gcTime: 10 * 60 * 1000, // 10 хвилин
    },
  },
});

const AppWithTheme: React.FC = () => {
  const { dark } = useContext(ThemeContext);

  useEffect(() => {
    document.body.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <ConfigProvider
      theme={{
        algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: "#1890ff",
          colorTextBase: dark ? "#d9d9d9" : "#333",
          colorBgBase: dark ? "#1a1a1a" : "#f5f5f5",
          colorBgContainer: dark ? "#2c2c2c" : "#fafafa",
          colorBorder: dark ? "#444444" : "#d9d9d9",
        },
      }}
    >
      <App />
    </ConfigProvider>
  );
};

const Root = () => {
  return (
    <React.StrictMode>
      <ErrorBoundary>
        <AuthProvider>
          <ThemeProvider>
            <TimezoneProvider>
              <PageTitleProvider>
                <QueryClientProvider client={queryClient}>
                  <BrowserRouter
                    future={{
                      v7_startTransition: true,
                      v7_relativeSplatPath: true,
                    }}
                  >
                    <AppWithTheme />
                  </BrowserRouter>
                </QueryClientProvider>
              </PageTitleProvider>
            </TimezoneProvider>
          </ThemeProvider>
        </AuthProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);
