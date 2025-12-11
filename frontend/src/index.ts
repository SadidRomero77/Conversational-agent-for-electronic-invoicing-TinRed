import { WhatsAppHandler } from "./whatsapp_handler";
import dotenv from "dotenv";

// Cargar variables de entorno
dotenv.config();

/**
 * Función principal de inicio
 */
async function main() {
  console.log("═══════════════════════════════════════════════");
  console.log("🤖 TinRed Invoice Agent - WhatsApp Frontend");
  console.log("═══════════════════════════════════════════════\n");

  // Validar variables de entorno críticas
  const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  console.log(`📡 Backend URL: ${backendUrl}`);

  // Verificar conectividad con backend
  try {
    console.log("🔍 Verificando conectividad con backend...");
    const response = await fetch(`${backendUrl}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      throw new Error(`Backend respondió con status ${response.status}`);
    }

    const health = await response.json();
    console.log(`✅ Backend disponible: ${health.service} v${health.version}\n`);
  } catch (error: any) {
    console.error("❌ No se pudo conectar con el backend:");
    console.error(`   ${error.message}`);
    console.error("\n🔧 Asegúrate de que el backend esté corriendo:");
    console.error("   cd backend && python -m app.main\n");
    process.exit(1);
  }

  // Inicializar handler de WhatsApp
  try {
    console.log("🚀 Iniciando conexión con WhatsApp...\n");
    const handler = new WhatsAppHandler();
    await handler.initSocket();
  } catch (error: any) {
    console.error("❌ Error al iniciar el agente:");
    console.error(`   ${error.message}`);
    console.error("\n🔧 Posibles causas:");
    console.error("   - No tienes permisos de lectura/escritura en la carpeta");
    console.error("   - Puerto en uso por otra aplicación");
    console.error("   - Problema de red\n");
    process.exit(1);
  }
}

// Manejo de señales de sistema
process.on("SIGINT", () => {
  console.log("\n\n🛑 Cerrando aplicación...");
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("\n\n🛑 Cerrando aplicación...");
  process.exit(0);
});

// Manejo de errores no capturados
process.on("uncaughtException", (error) => {
  console.error("❌ Error no capturado:", error);
  process.exit(1);
});

process.on("unhandledRejection", (reason, promise) => {
  console.error("❌ Promise rechazada no manejada:", reason);
  process.exit(1);
});

// Ejecutar
main().catch((err) => {
  console.error("❌ Error fatal al iniciar el agente:", err);
  process.exit(1);
});