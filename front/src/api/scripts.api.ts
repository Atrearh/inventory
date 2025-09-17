import { apiRequest } from "../utils/apiUtils";

export interface ScriptExecutionResult {
  Success?: boolean;
  Errors?: string[];
  Data?: {
    ProgramName?: string;
    Method?: string;
    Message?: string;
  };
  output?: string;
  error?: string;
}

export const updatePolicies = async (hostname: string) => {
  if (!hostname) {
    throw new Error("Hostname не вказано");
  }
  return apiRequest<ScriptExecutionResult>(
    "post",
    "/scripts/execute/updatePolicies.ps1",
    { hostname },
  );
};

export const restartPrintSpooler = async (hostname: string) => {
  if (!hostname) {
    throw new Error("Hostname не вказано");
  }
  return apiRequest<ScriptExecutionResult>(
    "post",
    "/scripts/execute/restartPrintSpooler.ps1",
    { hostname },
  );
};

export const getScriptsList = async (): Promise<string[]> => {
  return apiRequest<string[]>("get", "/scripts/list");
};

export const executeScript = async (
  hostname: string,
  scriptName: string,
  params: Record<string, any> = {},
): Promise<ScriptExecutionResult> => {
  if (!hostname) {
    throw new Error("Hostname не вказано");
  }
  return apiRequest<ScriptExecutionResult>(
    "post",
    `/scripts/execute/${scriptName}`,
    { hostname, ...params },
  );
};
