import { Component, ReactNode } from "react";
import { TFunction } from "i18next";
import { Result, Button } from "antd";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  t: TFunction<"translation", undefined>; // Додано проп для t
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    error: null,
  };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    const { t, fallback, children } = this.props;
    if (this.state.hasError) {
      return (
        fallback || (
          <Result
            status="error"
            title={t("error_boundary", "Something went wrong.")}
            subTitle={this.state.error?.message}
            extra={
              <Button type="primary" onClick={() => window.location.reload()}>
                {t("reload", "Reload")}
              </Button>
            }
          />
        )
      );
    }
    return children;
  }
}

export default ErrorBoundary;