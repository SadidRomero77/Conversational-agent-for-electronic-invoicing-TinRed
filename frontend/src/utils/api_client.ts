/**
 * Conecta con el backend FastAPI para enviar mensajes o archivos.
 */

import fetch from "node-fetch";
import dotenv from "dotenv";
dotenv.config();

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "dev-api-key";

// New shape for Factura as expected by the backend / Pydantic model
export interface FacturaItem {
  descripcion: string;
  cantidad: number;
  valorUnitario: number;
}

export interface FacturaTinred {
  numeroFactura: string;
  fechaEmision: string; // YYYY-MM-DD
  moneda: string;
  total: number;
  emisor: {
    nit: string;
    razonSocial: string;
    direccion?: string;
  };
  receptor: {
    nit: string;
    razonSocial: string;
    direccion?: string;
    correo?: string | null;
  };
  items: FacturaItem[];
}

/**
 * Envía la factura construida al backend.
 * Espera que el backend verifique y reenvíe a Tinred.
 */
export async function sendFacturaToBackend(factura: FacturaTinred) {
  const response = await fetch(`${BACKEND_URL}/api/tinred/enviar`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY
    },
    body: JSON.stringify(factura)
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backend error (${response.status}): ${text}`);
  }

  return await response.json();
}
