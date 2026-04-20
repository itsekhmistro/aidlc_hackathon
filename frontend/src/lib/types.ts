// ─── Domain types ────────────────────────────────────────────────────────────

export type PresenceStatus = "online" | "afk" | "offline";
export type RoomVisibility = "public" | "private";
export type MemberRole = "owner" | "admin" | "member";
export type FriendshipStatus = "pending" | "accepted";

export interface UserPublic {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface SessionPublic {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_seen_at: string;
}

export interface RoomPublic {
  id: string;
  name: string;
  description: string | null;
  visibility: RoomVisibility;
  owner_id: string;
  is_personal: boolean;
  created_at: string;
  member_count: number;
}

export interface RoomCreate {
  name: string;
  description?: string | null;
  visibility: RoomVisibility;
}

export interface RoomUpdate {
  name?: string | null;
  description?: string | null;
  visibility?: RoomVisibility | null;
}

export interface RoomMemberPublic {
  user_id: string;
  username: string;
  role: MemberRole;
  presence_status: PresenceStatus;
  joined_at: string;
}

export interface RoomBanPublic {
  user_id: string;
  username: string;
  banned_by_id: string;
  banned_by_username: string;
  banned_at: string;
}

export interface RoomInvitationPublic {
  id: string;
  room_id: string;
  invited_by_id: string;
  invited_user_id: string;
  created_at: string;
  accepted_at: string | null;
}

export interface AttachmentPublic {
  id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  comment: string | null;
  created_at: string;
}

export interface MessagePublic {
  id: string;
  room_id: string;
  author_id: string;
  author_username: string;
  content: string;
  reply_to_id: string | null;
  reply_preview: string | null;
  attachments: AttachmentPublic[];
  created_at: string;
  edited_at: string | null;
  deleted: boolean;
}

export interface MessageCreate {
  content: string;
  reply_to_id?: string | null;
}

export interface MessagePage {
  messages: MessagePublic[];
  has_more: boolean;
  next_cursor: string | null;
}

export interface FriendshipPublic {
  id: string;
  requester_id: string;
  requester_username: string;
  addressee_id: string;
  addressee_username: string;
  status: FriendshipStatus;
  message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UnreadCountsPublic {
  counts: Record<string, number>; // room_id → unread count
}

// ─── Auth request/response ────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
  persistent: boolean;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

// ─── WebSocket events ─────────────────────────────────────────────────────────

// Base
interface WsEventBase {
  type: string;
}

// Client → Server
export interface WsHeartbeat extends WsEventBase {
  type: "presence.heartbeat";
  tab_id: string;
  status: "online" | "afk";
}

export interface WsPing extends WsEventBase {
  type: "ping";
}

export type ClientEvent = WsHeartbeat | WsPing;

// Server → Client: Presence
export interface WsPresenceUpdate extends WsEventBase {
  type: "presence.update";
  user_id: string;
  status: PresenceStatus;
}

export interface WsPresenceBulk extends WsEventBase {
  type: "presence.bulk";
  presences: Array<{ user_id: string; status: PresenceStatus }>;
}

// Server → Client: Messages
export interface WsMessageNew extends WsEventBase {
  type: "message.new";
  room_id: string;
  message: MessagePublic;
}

export interface WsMessageEdited extends WsEventBase {
  type: "message.edited";
  room_id: string;
  message_id: string;
  content: string;
  edited_at: string;
}

export interface WsMessageDeleted extends WsEventBase {
  type: "message.deleted";
  room_id: string;
  message_id: string;
}

// Server → Client: Rooms
export interface WsRoomMemberJoined extends WsEventBase {
  type: "room.member_joined";
  room_id: string;
  user: RoomMemberPublic;
}

export interface WsRoomMemberLeft extends WsEventBase {
  type: "room.member_left";
  room_id: string;
  user_id: string;
}

export interface WsRoomMemberBanned extends WsEventBase {
  type: "room.member_banned";
  room_id: string;
  user_id: string;
  banned_by: string;
}

export interface WsRoomMemberUnbanned extends WsEventBase {
  type: "room.member_unbanned";
  room_id: string;
  user_id: string;
}

export interface WsRoomAdminGranted extends WsEventBase {
  type: "room.admin_granted";
  room_id: string;
  user_id: string;
}

export interface WsRoomAdminRemoved extends WsEventBase {
  type: "room.admin_removed";
  room_id: string;
  user_id: string;
}

export interface WsRoomUpdated extends WsEventBase {
  type: "room.updated";
  room_id: string;
  changes: Partial<RoomPublic>;
}

export interface WsRoomDeleted extends WsEventBase {
  type: "room.deleted";
  room_id: string;
}

export interface WsRoomInvitation extends WsEventBase {
  type: "room.invitation";
  room_id: string;
  room_name: string;
  invited_by: UserPublic;
}

// Server → Client: Friends
export interface WsFriendRequestReceived extends WsEventBase {
  type: "friend.request_received";
  friendship: FriendshipPublic;
}

export interface WsFriendAccepted extends WsEventBase {
  type: "friend.accepted";
  friendship: FriendshipPublic;
}

export interface WsFriendRemoved extends WsEventBase {
  type: "friend.removed";
  friendship_id: string;
}

export interface WsUserBanned extends WsEventBase {
  type: "user.banned";
  banner_id: string;
  banned_id: string;
}

// Server → Client: Notifications
export interface WsUnreadIncrement extends WsEventBase {
  type: "unread.increment";
  room_id: string;
  count: number;
}

export interface WsUnreadCleared extends WsEventBase {
  type: "unread.cleared";
  room_id: string;
}

// Server → Client: Session
export interface WsSessionRevoked extends WsEventBase {
  type: "session.revoked";
  session_id: string;
}

export interface WsPong extends WsEventBase {
  type: "pong";
}

// Discriminated union of ALL server events
export type ServerEvent =
  | WsPresenceUpdate
  | WsPresenceBulk
  | WsMessageNew
  | WsMessageEdited
  | WsMessageDeleted
  | WsRoomMemberJoined
  | WsRoomMemberLeft
  | WsRoomMemberBanned
  | WsRoomMemberUnbanned
  | WsRoomAdminGranted
  | WsRoomAdminRemoved
  | WsRoomUpdated
  | WsRoomDeleted
  | WsRoomInvitation
  | WsFriendRequestReceived
  | WsFriendAccepted
  | WsFriendRemoved
  | WsUserBanned
  | WsUnreadIncrement
  | WsUnreadCleared
  | WsSessionRevoked
  | WsPong;
