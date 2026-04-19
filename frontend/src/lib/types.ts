// Shared TypeScript types — extend as you build features

// Auth
export interface UserPublic {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
}

// WebSocket
export interface WsEvent {
  type: string;
  [key: string]: unknown;
}

export interface WsUserJoined extends WsEvent {
  type: "user_joined";
  client_id: string;
}

export interface WsUserLeft extends WsEvent {
  type: "user_left";
  client_id: string;
}

export interface WsMessage extends WsEvent {
  type: "message";
  from: string;
  payload: unknown;
}

export interface WsPong extends WsEvent {
  type: "pong";
}

export type ServerEvent = WsUserJoined | WsUserLeft | WsMessage | WsPong;
