import { useCallback, useEffect, useRef, useState } from "react";

export type ReadyState = "connecting" | "open" | "closing" | "closed";

interface UseWebSocketOptions<T> {
  onMessage?: (data: T) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (event: Event) => void;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn<T> {
  sendMessage: (data: object) => void;
  lastMessage: T | null;
  readyState: ReadyState;
  disconnect: () => void;
}

export function useWebSocket<T = unknown>(
  url: string,
  options: UseWebSocketOptions<T> = {}
): UseWebSocketReturn<T> {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectDelay = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [readyState, setReadyState] = useState<ReadyState>("connecting");
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const intentionalClose = useRef(false);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setReadyState("connecting");

    ws.onopen = () => {
      setReadyState("open");
      reconnectAttempts.current = 0;
      onOpen?.();
    };

    ws.onmessage = (event: MessageEvent) => {
      const data = JSON.parse(event.data as string) as T;
      setLastMessage(data);
      onMessage?.(data);
    };

    ws.onclose = () => {
      setReadyState("closed");
      onClose?.();
      if (!intentionalClose.current && reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        setTimeout(connect, reconnectDelay);
      }
    };

    ws.onerror = (event: Event) => {
      onError?.(event);
    };
  }, [url, onMessage, onOpen, onClose, onError, reconnectDelay, maxReconnectAttempts]);

  useEffect(() => {
    intentionalClose.current = false;
    connect();
    return () => {
      intentionalClose.current = true;
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    wsRef.current?.close();
  }, []);

  return { sendMessage, lastMessage, readyState, disconnect };
}
