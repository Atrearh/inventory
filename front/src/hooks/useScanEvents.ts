// src/hooks/useScanEvents.ts
import { useEffect, useState } from "react";

export interface ScanEvent {
  task_id: string;
  status: string;
  progress?: number;
  message?: string;
}

export function useScanEvents() {
  const [events, setEvents] = useState<ScanEvent[]>([]);

  useEffect(() => {
    const eventSource = new EventSource("/api/scan/events"); // бекенд має віддавати SSE
    eventSource.onmessage = (e) => {
      const data: ScanEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, data]);
    };
    eventSource.onerror = () => {
      console.error("SSE connection error");
      eventSource.close();
    };
    return () => eventSource.close();
  }, []);

  return events;
}
