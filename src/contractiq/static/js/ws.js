/**
 * WebSocket client manager for ContractIQ real-time streaming and notifications.
 */

class WebSocketClient {
  constructor() {
    this.querySocket = null;
    this.notifSocket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
  }

  connectNotifications(onMessageCallback) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/notifications`;

    try {
      this.notifSocket = new WebSocket(url);

      this.notifSocket.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        console.log("[ContractIQ WS] Connected to push notification stream");
      };

      this.notifSocket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (onMessageCallback) onMessageCallback(payload);
        } catch (e) {
          console.debug("[ContractIQ WS] Non-JSON payload", event.data);
        }
      };

      this.notifSocket.onclose = () => {
        this.isConnected = false;
        if (this.reconnectAttempts < 5) {
          this.reconnectAttempts++;
          setTimeout(() => this.connectNotifications(onMessageCallback), 3000);
        }
      };
    } catch (err) {
      console.warn("[ContractIQ WS] Notification socket init failed", err);
    }
  }
}

window.wsClient = new WebSocketClient();
