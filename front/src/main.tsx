import { ConfigProvider, theme } from "antd";
import React, { useEffect, useMemo} from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./components/i18n";
import "./index.css";
import { AppProvider, useAppContext } from "./context/AppContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
    },
    mutations: {
      onError: (error) => { 
        console.error("Global query error:", error);
      },
    },
  },
});

const AppWithTheme: React.FC = () => {
  const { dark } = useAppContext();
  const themeObj = useMemo(() => ({ 
    algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: "#1890ff",
      colorTextBase: dark ? "#d9d9d9" : "#333",
      colorBgBase: dark ? "#1a1a1a" : "#f5f5f5",
      colorBgContainer: dark ? "#2c2c2c" : "#fafafa",
      colorBorder: dark ? "#444444" : "#d9d9d9",
    },
  }), [dark]);

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
  return (
    <React.StrictMode>
      <ErrorBoundary>
        <AppProvider>
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
        </AppProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);