import{
  createContext as createReactContext,
  useContext,
  ReactNode,
  FC,
} from "react";
import React from "react";

interface ContextConfig<T> {
  name: string;
}

export function createCustomContext<T>() {
  return (config: ContextConfig<T>) => {
    const Context = createReactContext<T | null>(null);

    interface ProviderProps {
      children: ReactNode;
      value: T;
    }

    const Provider: FC<ProviderProps> = ({ children, value }) => React.createElement(Context.Provider, { value }, children);

    const useContextHook = (): T => {
      const context = useContext(Context);
      if (context === null) {
        throw new Error(
          `${config.name} must be used within a ${config.name}Provider`,
        );
      }
      return context;
    };

    return [Context, Provider, useContextHook] as const;
  };
}
