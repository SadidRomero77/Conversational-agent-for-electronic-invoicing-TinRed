/**
 * Limpia y unifica el contenido textual del mensaje entrante de WhatsApp.
 */

export type Intent = "greeting" | "emit_invoice" | "unknown";

function detectIntent(text: string): Intent {
  const t = (text || "").toLowerCase();

  // Greetings
  const greetings = ["hola", "buenos", "buenas", "saludos", "buen dia", "buen día", "buenas tardes", "buenas noches"];
  for (const g of greetings) {
    if (t.includes(g)) return "greeting";
  }

  // Emit invoice intents (spanish patterns)
  const invoicePatterns = ["factura", "emitir factura", "generar factura", "quiero facturar", "necesito factura", "hacer factura", "facturación"];
  for (const p of invoicePatterns) {
    if (t.includes(p)) return "emit_invoice";
  }

  return "unknown";
}

/**
 * Limpia y unifica el contenido textual del mensaje entrante y detecta la intención.
 */
export function parseMessage(msg: any): { text: string; intent: Intent } {
  const text =
    msg.message.conversation ||
    msg.message.extendedTextMessage?.text ||
    msg.message.imageMessage?.caption ||
    msg.message.audioMessage?.caption ||
    "";

  const trimmed = text.trim();
  const intent = detectIntent(trimmed);

  return { text: trimmed, intent };
}
