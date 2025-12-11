"""
Cliente HTTP para TinRed Suite API.
ACTUALIZADO: Incluye validación de clientes (checkclient_agente_ai)
"""
import logging
import requests
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.models.schemas import ClientIdentification, InvoiceResponse, InvoiceItem

logger = logging.getLogger(__name__)


class TinRedAPIError(Exception):
    pass


class TinRedClient:
    def __init__(self):
        self.timeout = settings.TINRED_TIMEOUT  # Timeout general (30s)
        self.emission_timeout = 90  # Timeout para emisión (90s) - más lento
        self.verify_ssl = settings.TINRED_VERIFY_SSL
        self.headers = {"Content-Type": "application/json"}
        
        # URL para validación de clientes
        self.check_client_url = getattr(
            settings, 
            'TINRED_CHECK_CLIENT_URL', 
            'https://test.tinred.pe/SisFact/api/checkclient_agente_ai'
        )
    
    def _request(self, method: str, url: str, json_data: Dict = None, timeout: int = None) -> Dict:
        """Realiza petición HTTP con timeout configurable."""
        request_timeout = timeout or self.timeout
        try:
            logger.info(f"[TinRed] {method} {url} (timeout: {request_timeout}s)")
            response = requests.request(
                method, url, json=json_data, 
                headers=self.headers, 
                timeout=request_timeout,  # ← Timeout configurable
                verify=self.verify_ssl
            )
            
            try:
                data = response.json()
            except:
                raise TinRedAPIError("Respuesta inválida")
            
            if response.status_code >= 400:
                raise TinRedAPIError(data.get('mensaje', f'Error {response.status_code}'))
            
            return data
        except requests.exceptions.Timeout:
            raise TinRedAPIError("Timeout")
        except requests.exceptions.ConnectionError:
            raise TinRedAPIError("Sin conexión")
        except TinRedAPIError:
            raise
        except Exception as e:
            raise TinRedAPIError(str(e))
    
    def check_client(self, phone: str, document_number: str) -> Tuple[bool, str]:
        """
        Valida si un cliente existe en TinRed/SUNAT.
        
        Args:
            phone: Teléfono del usuario autenticado
            document_number: DNI o RUC del cliente a validar
            
        Returns:
            Tuple[bool, str]: (existe, nombre_o_mensaje)
            - Si existe: (True, "NOMBRE DEL CLIENTE")
            - Si no existe: (False, "Cliente no encontrado")
        """
        clean_phone = phone.split("@")[0].replace(" ", "").replace("-", "")
        
        payload = {
            "telefono": clean_phone,
            "numero_documento": document_number
        }
        
        logger.info(f"[TinRed] 🔍 Validando cliente: {document_number}")
        
        try:
            response = self._request("POST", self.check_client_url, payload)
            
            # Respuesta esperada:
            # {"01": "NOMBRE DEL CLIENTE"} si existe
            # {"00": "Cliente no encontrado"} si no existe
            
            if "01" in response:
                client_name = response["01"]
                logger.info(f"[TinRed] ✅ Cliente encontrado: {client_name}")
                return (True, client_name)
            
            elif "00" in response:
                message = response["00"]
                logger.info(f"[TinRed] ❌ Cliente no encontrado: {message}")
                return (False, message)
            
            else:
                # Respuesta inesperada, intentar extraer información
                logger.warning(f"[TinRed] ⚠️ Respuesta inesperada: {response}")
                # Verificar si hay algún valor que indique éxito
                for key, value in response.items():
                    if key != "00" and isinstance(value, str) and len(value) > 2:
                        return (True, value)
                return (False, "Respuesta no reconocida del servidor")
        
        except TinRedAPIError as e:
            logger.error(f"[TinRed] ❌ Error validando cliente: {e}")
            # En caso de error de conexión, permitir continuar pero advertir
            return (False, f"Error de conexión: {str(e)}")
        
        except Exception as e:
            logger.error(f"[TinRed] ❌ Error inesperado: {e}")
            return (False, f"Error inesperado: {str(e)}")
    
    def identify_client(self, phone: str) -> ClientIdentification:
        clean = phone.split("@")[0].replace(" ", "").replace("-", "")
        logger.info(f"[TinRed] Identificando: {clean}")
        response = self._request("POST", settings.TINRED_IDENTIFY_URL, {"telefono": clean})
        if "IdEmpresa" not in response:
            raise TinRedAPIError("No registrado")
        client = ClientIdentification(**response)
        logger.info(f"[TinRed] ✅ {client.Nombre}")
        return client
    
    def emit_invoice(
        self, client_data: ClientIdentification, document_type: str,
        currency: str, id_type: str, id_number: str, items: List[InvoiceItem]
    ) -> InvoiceResponse:
        total = sum(item.subtotal() for item in items)
        
        payload = {
            "idEmpresa": client_data.IdEmpresa,
            "idEstablecimiento": client_data.IdEstablecimiento or "0001",
            "idUsuario": str(client_data.IdUsuario),
            "tdocod": document_type,
            "mondoc": currency,
            "tdicod": id_type,
            "clinum": id_number,
            "cant": [str(int(float(item.cantidad))) for item in items],
            "detpro": [item.descripcion for item in items],
            "preuni": [f"{float(item.precio):.2f}" for item in items],
            "total": f"{total:.2f}"
        }
        
        tipo = "Factura" if document_type == "01" else "Boleta"
        logger.info(f"[TinRed] 🚀 {tipo}")
        logger.info(f"[TinRed] Payload: {payload}")
        
        # Usar timeout extendido para emisión (es más lento)
        response = self._request("POST", settings.TINRED_STORE_URL, payload, timeout=self.emission_timeout)
        logger.info(f"[TinRed] Respuesta: {response}")
        
        return InvoiceResponse(
            success=response.get("success", "FALSE"),
            estado=response.get("estado", ""),
            serie=response.get("serie", ""),
            numero=response.get("numero", ""),
            id=response.get("id", 0),
            mensaje=response.get("mensaje", ""),
            pdf=response.get("pdf", "")
        )
    
    def get_clients(self, phone: str) -> List[Dict]:
        try:
            r = self._request("POST", settings.TINRED_CLIENT_LIST_URL, {"telefono": phone.split("@")[0]})
            return r if isinstance(r, list) else []
        except:
            return []
    
    def get_products(self, phone: str) -> List[Dict]:
        try:
            r = self._request("POST", settings.TINRED_PRODUCT_LIST_URL, {"telefono": phone.split("@")[0]})
            return r if isinstance(r, list) else []
        except:
            return []
    
    def get_history(self, phone: str) -> List[Dict]:
        try:
            r = self._request("POST", settings.TINRED_HISTORY_URL, {"telefono": phone.split("@")[0]})
            return r if isinstance(r, list) else []
        except:
            return []


_client: Optional[TinRedClient] = None

def get_tinred_client() -> TinRedClient:
    global _client
    if _client is None:
        _client = TinRedClient()
    return _client


