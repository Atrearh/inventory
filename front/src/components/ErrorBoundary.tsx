// src/components/ErrorBoundary.tsx
import { Component, ReactNode } from "react";
import { notification } from "antd";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
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
    notification.error({
      message: "Произошла ошибка",
      description: error.message,
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div style={{ padding: 16, color: "#ff4d4f" }}>
            <h2>Что-то пошло не так</h2>
            <p>{this.state.error?.message}</p>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
