import P from "pino";
import * as QRCode from "qrcode";
import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  WASocket,
  downloadMediaMessage,
  getContentType,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import { createWriteStream, readFileSync, rmSync, existsSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import fetch from "node-fetch";

// Configuración
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT = 30000; // 30 segundos
const MAX_QR_ATTEMPTS = 3;

/**
 * Convierte un archivo a Base64
 */
function fileToBase64(path: string): string {
  const fileBuffer = readFileSync(path);
  return fileBuffer.toString("base64");
}

/**
 * Manejador de WhatsApp con Baileys
 */
class WhatsAppHandler {
  private sock!: WASocket;
  private qrAttempts = 0;
  private readonly maxQrAttempts = MAX_QR_ATTEMPTS;
  private saveCreds!: () => Promise<void>;
  private logger = P({ level: "info" });

  /**
   * Inicializa el socket de WhatsApp
   */
  async initSocket() {
    try {
      const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");
      this.saveCreds = saveCreds;

      const { version } = await fetchLatestBaileysVersion();
      
      this.logger.info(`Inicializando WhatsApp con Baileys v${version.join(".")}`);

      this.sock = makeWASocket({
        version,
        printQRInTerminal: false,
        auth: state,
        browser: ["TinRed Agent", "Chrome", "1.0.0"],
        syncFullHistory: false,
        logger: P({ level: "silent" }), // Silenciar logs internos de Baileys
      });

      // Registrar eventos
      this.sock.ev.on("creds.update", this.onCredsUpdate.bind(this));
      this.sock.ev.on("messages.upsert", this.onMessagesUpsert.bind(this));
      this.sock.ev.on("connection.update", this.onConnectionUpdate.bind(this));

      this.logger.info("Socket de WhatsApp inicializado correctamente");
    } catch (error) {
      this.logger.error(`Error al inicializar socket: ${error}`);
      throw error;
    }
  }

  /**
   * Guarda las credenciales actualizadas
   */
  private async onCredsUpdate() {
    await this.saveCreds();
  }

  /**
   * Descarga y guarda un archivo de medios
   */
  private async downloadAndSaveMedia(stream: any, filepath: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const writeStream = createWriteStream(filepath);
      stream.pipe(writeStream);
      writeStream.on("finish", () => resolve());
      writeStream.on("error", (err) => reject(err));
    });
  }

  /**
   * Envía indicador de "escribiendo..." al usuario
   */
  private async sendTypingIndicator(jid: string, isTyping: boolean = true) {
    try {
      await this.sock.sendPresenceUpdate(isTyping ? "composing" : "paused", jid);
    } catch (error) {
      this.logger.warn(`No se pudo enviar indicador de escritura: ${error}`);
    }
  }

  /**
   * Envía mensaje al backend con timeout y retry
   */
  private async sendToBackend(
    jid: string,
    messageText: string,
    mimeType: string = "",
    fileBase64: string | null = null
  ): Promise<string> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

    try {
      this.logger.info(`[${jid}] Enviando mensaje al backend: "${messageText.substring(0, 50)}..."`);

      const response = await fetch(`${BACKEND_URL}/api/converse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          phone: jid,
          mime_type: mimeType,
          file_base64: fileBase64,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Backend respondió con status ${response.status}`);
      }

      const data: any = await response.json();
      
      this.logger.info(`[${jid}] Respuesta recibida del backend`);
      
      return data.reply || "⚠️ No pude procesar tu mensaje. Intenta nuevamente.";

    } catch (error: any) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        this.logger.error(`[${jid}] Timeout al conectar con backend`);
        return "⏱️ La solicitud tardó demasiado. Por favor intenta nuevamente.";
      }

      this.logger.error(`[${jid}] Error al comunicarse con backend: ${error.message}`);
      return "❌ No pude conectar con el servidor. Verifica que el backend esté funcionando.";
    }
  }

  /**
   * Procesa mensajes entrantes
   */
  private async onMessagesUpsert(message_array: any) {
    for (const msg of message_array.messages) {
      // Ignorar mensajes propios
      if (msg.key.fromMe) continue;
      if (!msg.message) continue;

      const messageType = getContentType(msg.message);
      const jid = msg.key.remoteJid;

      this.logger.info(`[${jid}] Mensaje recibido (tipo: ${messageType})`);

      let messageText = msg.message.conversation || msg.message.extendedTextMessage?.text || "";
      let mimeType = "";
      let filename = "";
      let fileBase64: string | null = null;

      try {
        // Procesar AUDIO
        if (messageType === "audioMessage") {
          this.logger.info(`[${jid}] Procesando audio...`);
          
          mimeType = msg.message.audioMessage.mimetype;
          const extension = mimeType.includes("ogg") ? "ogg" : "mp3";
          filename = join(tmpdir(), `audio-${Date.now()}.${extension}`);

          const stream = await downloadMediaMessage(
            msg,
            "stream",
            {},
            {
              logger: P({ level: "silent" }),
              reuploadRequest: this.sock.updateMediaMessage,
            }
          );

          await this.downloadAndSaveMedia(stream, filename);
          fileBase64 = fileToBase64(filename);
          
          this.logger.info(`[${jid}] Audio descargado (${mimeType})`);

          // Limpiar archivo temporal
          try {
            rmSync(filename);
          } catch {}
        }

        // Procesar IMAGEN (opcional, si quieres usarlas)
        if (messageType === "imageMessage") {
          this.logger.info(`[${jid}] Imagen recibida (no procesada actualmente)`);
          messageText = msg.message.imageMessage.caption || "📷 [Imagen]";
          // Si quieres procesar imágenes, descomenta esto:
          /*
          mimeType = msg.message.imageMessage.mimetype;
          filename = join(tmpdir(), `image-${Date.now()}.jpg`);
          const stream = await downloadMediaMessage(msg, "stream", {}, {
            logger: P({ level: "silent" }),
            reuploadRequest: this.sock.updateMediaMessage,
          });
          await this.downloadAndSaveMedia(stream, filename);
          fileBase64 = fileToBase64(filename);
          rmSync(filename);
          */
        }

        // Enviar indicador de "escribiendo..."
        await this.sendTypingIndicator(jid, true);

        // Enviar al backend y obtener respuesta
        const reply = await this.sendToBackend(jid, messageText, mimeType, fileBase64);

        // Detener indicador de escritura
        await this.sendTypingIndicator(jid, false);

        // Enviar respuesta al usuario
        await this.sock.sendMessage(jid, { text: reply });

        // Marcar mensaje como leído
        await this.sock.readMessages([msg.key]);

        this.logger.info(`[${jid}] Respuesta enviada exitosamente`);

      } catch (error: any) {
        this.logger.error(`[${jid}] Error procesando mensaje: ${error.message}`);
        
        // Enviar mensaje de error al usuario
        try {
          await this.sock.sendMessage(jid, {
            text: "❌ Ocurrió un error al procesar tu mensaje. Por favor intenta nuevamente.",
          });
        } catch {}
      }
    }
  }

  /**
   * Maneja actualizaciones de conexión
   */
  private async onConnectionUpdate(update: {
    connection?: string;
    lastDisconnect?: { error: any };
    qr?: string;
  }) {
    const { connection, lastDisconnect, qr } = update;

    // Mostrar QR code
    if (qr) {
      this.qrAttempts++;

      if (this.qrAttempts > this.maxQrAttempts) {
        this.logger.error("Máximo de intentos de QR alcanzado. Cerrando...");
        await this.sock.logout();
        process.exit(1);
        return;
      }

      QRCode.toString(qr, { type: "terminal", small: true }, (err, url) => {
        if (err) {
          this.logger.error(`Error generando QR: ${err}`);
          return;
        }
        console.log(url);
        this.logger.info(`📱 Escanea el código QR (${this.qrAttempts}/${this.maxQrAttempts})`);
      });
    }

    // Conexión establecida
    if (connection === "open") {
      this.logger.info("✅ Conectado a WhatsApp exitosamente");
      this.qrAttempts = 0; // Reset contador de QR
    }

    // Conexión cerrada
    if (connection === "close") {
      const statusCode = (lastDisconnect?.error as any)?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

      this.logger.warn(`Conexión cerrada. Código: ${statusCode}`);

      if (shouldReconnect) {
        this.logger.info("Reconectando...");
        await this.initSocket();
      } else {
        this.logger.info("Sesión cerrada por logout. Limpiando credenciales...");
        this.deleteAuthFolder("auth_info_baileys");
        process.exit(0);
      }
    }
  }

  /**
   * Elimina la carpeta de autenticación
   */
  private deleteAuthFolder(folderName: string) {
    const fullPath = join(process.cwd(), folderName);
    if (existsSync(fullPath)) {
      rmSync(fullPath, { recursive: true, force: true });
      this.logger.info(`Carpeta de autenticación eliminada: ${fullPath}`);
    }
  }
}

export { WhatsAppHandler };