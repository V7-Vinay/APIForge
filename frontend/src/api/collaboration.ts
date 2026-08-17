import type {
  CollaborationEvent,
  CollaborationPresence,
  ConnectionState,
} from "../types/api";

type Handlers = {
  onEvent?: (event: CollaborationEvent) => void;
  onPresence?: (presence: CollaborationPresence[]) => void;
  onStateChange?: (state: ConnectionState) => void;
  onError?: (message: string) => void;
};

export class CollaborationClient {
  private socket: WebSocket | null = null;
  private heartbeat: number | null = null;
  private reconnectTimer: number | null = null;
  private closedIntentionally = false;
  private joinedRequestId: string | null = null;
  private reconnectAttempts = 0;

  constructor(
    private workspaceId: string,
    private getToken: () => string | null,
    private handlers: Handlers = {},
  ) {}

  connect() {
    this.closedIntentionally = false;
    this.open();
  }

  disconnect() {
    this.closedIntentionally = true;
    this.clearTimers();
    this.socket?.close();
    this.socket = null;
    this.handlers.onStateChange?.("DISCONNECTED");
  }

  joinRequest(requestId: string) {
    this.joinedRequestId = requestId;
    this.send({ type: "JOIN_REQUEST", request_id: requestId });
  }

  leaveRequest(requestId?: string) {
    const id = requestId ?? this.joinedRequestId;
    if (id) this.send({ type: "LEAVE_REQUEST", request_id: id });
    this.joinedRequestId = null;
  }

  private open() {
    const token = this.getToken();
    if (!token) {
      this.handlers.onStateChange?.("DISCONNECTED");
      return;
    }

    this.handlers.onStateChange?.(
      this.reconnectAttempts > 0 ? "RECONNECTING" : "DISCONNECTED",
    );

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/api/v1/workspaces/${this.workspaceId}/collaboration`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "AUTH", token }));
    };

    socket.onmessage = (message) => {
      let event: CollaborationEvent;
      try {
        event = JSON.parse(message.data) as CollaborationEvent;
      } catch {
        return;
      }

      if (event.type === "AUTHENTICATED") {
        this.reconnectAttempts = 0;
        this.handlers.onStateChange?.("CONNECTED");
        this.startHeartbeat();
        if (this.joinedRequestId) {
          this.send({ type: "JOIN_REQUEST", request_id: this.joinedRequestId });
        }
      }

      if (event.type === "PRESENCE_SNAPSHOT") {
        const users = (event.payload?.users ??
          event.payload?.presence ??
          []) as CollaborationPresence[];
        this.handlers.onPresence?.(users);
      }

      if (
        event.type === "USER_JOINED_REQUEST" ||
        event.type === "USER_LEFT_REQUEST"
      ) {
        // Presence snapshot usually follows; still notify.
      }

      if (event.type === "ERROR") {
        const msg =
          typeof event.payload?.message === "string"
            ? event.payload.message
            : "Collaboration error";
        this.handlers.onError?.(msg);
      }

      this.handlers.onEvent?.(event);
    };

    socket.onclose = () => {
      this.clearHeartbeat();
      if (this.closedIntentionally) {
        this.handlers.onStateChange?.("DISCONNECTED");
        return;
      }
      this.handlers.onStateChange?.("RECONNECTING");
      this.scheduleReconnect();
    };

    socket.onerror = () => {
      // onclose handles reconnect
    };
  }

  private send(payload: Record<string, unknown>) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private startHeartbeat() {
    this.clearHeartbeat();
    this.heartbeat = window.setInterval(() => {
      this.send({ type: "PING" });
    }, 15000);
  }

  private clearHeartbeat() {
    if (this.heartbeat) {
      window.clearInterval(this.heartbeat);
      this.heartbeat = null;
    }
  }

  private clearTimers() {
    this.clearHeartbeat();
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private scheduleReconnect() {
    this.clearTimers();
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000);
    this.reconnectAttempts += 1;
    this.reconnectTimer = window.setTimeout(() => this.open(), delay);
  }
}
