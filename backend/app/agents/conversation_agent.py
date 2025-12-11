"""
Conversation Agent - v6: Contexto sticky y selección de productos para emisión.
"""
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
import google.generativeai as genai
from app.models.schemas import UserSession, IntentType
from app.core.config import settings
from app.core.prompts import SYSTEM_PROMPT, build_rag_context

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GOOGLE_API_KEY)


class ConversationAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=settings.MODEL_NAME,
            generation_config={"temperature": 0.7, "max_output_tokens": 1024}
        )
        logger.info("[ConversationAgent] ✅ Inicializado")
    
    def handle_query(self, message: str, intent: IntentType, session: UserSession) -> str:
        logger.info(f"[ConversationAgent] {intent.value}: {message[:40]}...")
        
        msg_lower = message.lower().strip()
        
        # Obtener contexto guardado en sesión
        ctx = session.conversation_context
        logger.info(f"[ConversationAgent] Contexto sesión: {ctx}")
        
        # =========================================================
        # CASO: Usuario dice "Sí" después de ver un producto
        # =========================================================
        if ctx == "product_detail" and session.selected_product:
            if self._is_affirmative(msg_lower):
                return self._start_emission_with_product(session)
        
        # =========================================================
        # CASO: Solo un número - depende del contexto
        # =========================================================
        if re.match(r'^\d{1,2}$', message.strip()):
            number = int(message.strip())
            return self._handle_number_selection(number, session)
        
        # =========================================================
        # CASO: Búsqueda de productos
        # =========================================================
        if self._is_product_search(msg_lower):
            search_term = self._extract_search_term(msg_lower)
            if search_term:
                return self._search_products(search_term, session)
        
        # =========================================================
        # CASO: Contexto de búsqueda activo + texto (continuar búsqueda)
        # =========================================================
        if ctx == "search_results" and len(msg_lower) > 2:
            if not self._is_command(msg_lower):
                # Interpretar como nueva búsqueda
                return self._search_products(msg_lower, session)
        
        # =========================================================
        # CASO: Detalles de historial específico
        # =========================================================
        detail_number = self._extract_detail_number(msg_lower)
        if detail_number:
            return self._get_history_detail(detail_number, session)
        
        # =========================================================
        # CASO: "Detalles de la última" o "la de hoy"
        # =========================================================
        if self._asks_for_last(msg_lower) or self._asks_for_today(msg_lower):
            if session.session_emissions:
                return self._format_today_emission_detail(session.session_emissions[-1])
            if session.context.history:
                return self._get_history_detail(1, session)
            return "No tienes emisiones registradas."
        
        # =========================================================
        # CASO: Preguntas sobre diferencias factura/boleta
        # =========================================================
        if 'diferencia' in msg_lower and ('factura' in msg_lower or 'boleta' in msg_lower):
            return self._explain_invoice_difference()
        
        # =========================================================
        # CASO: Ver productos
        # =========================================================
        if intent == IntentType.QUERY_PRODUCTS or 'producto' in msg_lower:
            return self._list_products(session, msg_lower)
        
        # =========================================================
        # CASO: Ver historial
        # =========================================================
        if intent == IntentType.QUERY_HISTORY:
            return self._list_history(session)
        
        # =========================================================
        # CASO: Preguntas generales
        # =========================================================
        if intent == IntentType.GENERAL_QUESTION:
            return self._handle_general_question(message, session)
        
        # =========================================================
        # FALLBACK: Usar LLM
        # =========================================================
        return self._query_llm(message, intent, session)
    
    def _handle_number_selection(self, number: int, session: UserSession) -> str:
        """Maneja selección por número según el contexto."""
        ctx = session.conversation_context
        
        logger.info(f"[ConversationAgent] Número {number} en contexto: {ctx}")
        
        # Prioridad 1: Resultados de búsqueda
        if ctx == "search_results" and session.search_results:
            if number <= len(session.search_results):
                product = session.search_results[number - 1]
                return self._show_product_detail(product, number, session, from_search=True)
            return f"No encontré el resultado #{number}. Hay {len(session.search_results)} resultados."
        
        # Prioridad 2: Historial
        if ctx == "history":
            if session.context.history and number <= len(session.context.history):
                # Mantener contexto de historial
                session.set_context("history")
                return self._get_history_detail(number, session)
            return f"No encontré la emisión #{number}."
        
        # Prioridad 3: Productos
        if ctx == "products":
            if session.context.products and number <= len(session.context.products):
                product = session.context.products[number - 1]
                return self._show_product_detail(product, number, session)
            return f"No encontré el producto #{number}."
        
        # Prioridad 4: Emisiones de hoy
        if ctx == "today_emissions":
            if session.session_emissions and number <= len(session.session_emissions):
                return self._format_today_emission_detail(session.session_emissions[number - 1])
        
        # Sin contexto claro - intentar inferir
        return f"No entendí el #{number}. ¿Qué deseas ver?\n📦 Productos | 📊 Historial"
    
    def _show_product_detail(self, product: Dict, index: int, session: UserSession, from_search: bool = False) -> str:
        """Muestra detalle de un producto y guarda para posible emisión."""
        nombre = product.get('pronom', 'Sin nombre')
        precio = product.get('provun', '0')
        unidad = product.get('promed', 'Unidad')
        codigo = product.get('procod', '')
        
        try:
            precio = f"{float(precio):.2f}"
        except:
            pass
        
        # Guardar producto seleccionado
        session.selected_product = product
        session.set_context("product_detail")
        
        response = f"""📦 **Producto #{index}**

📋 **Nombre:** {nombre}
💰 **Precio:** S/{precio}
📏 **Unidad:** {unidad}"""
        
        if codigo:
            response += f"\n🏷️ **Código:** {codigo}"
        
        response += "\n\n¿Deseas emitir un comprobante con este producto? (Sí/No)"
        
        return response
    
    def _start_emission_with_product(self, session: UserSession) -> str:
        """Inicia emisión con el producto seleccionado."""
        product = session.selected_product
        
        if not product:
            return "No hay producto seleccionado. ¿Qué producto deseas emitir?"
        
        nombre = product.get('pronom', 'Producto')
        precio = product.get('provun', '0')
        
        try:
            precio_float = float(precio)
        except:
            precio_float = 0
        
        # Limpiar contexto de producto
        session.set_context("emission")
        
        # Guardar producto en pending_items para el emission_agent
        session.pending_items = [{
            "descripcion": nombre,
            "precio": str(precio_float),
            "cantidad": "1"
        }]
        
        return f"""✅ Producto seleccionado: **{nombre}** (S/{precio_float:.2f})

¿Qué tipo de comprobante deseas?
📄 **Factura** (requiere RUC)
🧾 **Boleta** (DNI o RUC)

Escribe "Factura" o "Boleta":"""
    
    def _is_affirmative(self, msg_lower: str) -> bool:
        """Detecta respuestas afirmativas."""
        affirmatives = ['si', 'sí', 'yes', 'ok', 'okey', 'dale', 'claro', 
                       'por supuesto', 'adelante', 'confirmo', 'acepto', 'listo']
        return any(msg_lower.strip().startswith(a) for a in affirmatives)
    
    def _is_command(self, msg_lower: str) -> bool:
        """Detecta si es un comando explícito."""
        commands = ['historial', 'productos', 'factura', 'boleta', 'emitir', 
                   'cancelar', 'ayuda', 'menú', 'menu']
        return any(c in msg_lower for c in commands)
    
    def _is_product_search(self, msg_lower: str) -> bool:
        """Detecta si es una búsqueda de productos."""
        search_keywords = ['busca', 'buscar', 'encuentra', 'encontrar', 'filtrar', 
                         'hay', 'tiene', 'tengo', 'existe']
        return any(kw in msg_lower for kw in search_keywords)
    
    def _extract_search_term(self, msg_lower: str) -> Optional[str]:
        """Extrae el término de búsqueda."""
        search_patterns = [
            r'busca(?:r)?\s+(.+)',
            r'encuentra(?:r)?\s+(.+)',
            r'filtrar?\s+(.+)',
            r'hay\s+(.+)',
            r'tiene[ns]?\s+(.+)',
            r'tengo\s+(.+)',
            r'existe[n]?\s+(.+)',
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                term = match.group(1).strip()
                term = re.sub(r'^(un|una|el|la|los|las|mis|en|productos?)\s+', '', term)
                return term if len(term) > 1 else None
        
        return None
    
    def _search_products(self, search_term: str, session: UserSession) -> str:
        """Busca productos y guarda resultados."""
        products = session.context.products
        
        if not products:
            return "📦 No tienes productos registrados."
        
        search_lower = search_term.lower()
        matches = [p for p in products if search_lower in p.get('pronom', '').lower()]
        
        if not matches:
            session.set_context("products")  # Volver a productos
            return f"""🔍 No encontré productos con "{search_term}".

Tienes {len(products)} productos en total.

💡 Prueba con otro término o "ver productos" para la lista."""
        
        # Guardar resultados de búsqueda
        session.set_context("search_results", search_results=matches)
        
        response = f"🔍 **Resultados para \"{search_term}\"** ({len(matches)}):\n\n"
        
        for i, p in enumerate(matches[:10], 1):
            nombre = p.get('pronom', 'Sin nombre')
            precio = p.get('provun', '0')
            try:
                precio = f"{float(precio):.2f}"
            except:
                pass
            
            response += f"{i}. {nombre}"
            if precio and precio != "0.00":
                response += f" - S/{precio}"
            response += "\n"
        
        if len(matches) > 10:
            response += f"\n... y {len(matches) - 10} más."
        
        response += "\n\n💡 Escribe un número para ver detalle y emitir."
        
        return response
    
    def _asks_for_last(self, msg_lower: str) -> bool:
        """Detecta si pide la última emisión."""
        patterns = [
            r'\b(última|ultimo|ultima|último)\b',
            r'\bdetalle[s]?\s+(?:de\s+)?(?:la|el)\s+(?:última|ultimo|ultima)\b',
        ]
        return any(re.search(p, msg_lower) for p in patterns)
    
    def _asks_for_today(self, msg_lower: str) -> bool:
        """Detecta si pregunta por emisiones de hoy."""
        today_keywords = ['de hoy', 'la de hoy', 'el de hoy', 'emitida hoy', 'generada hoy']
        return any(kw in msg_lower for kw in today_keywords)
    
    def _extract_detail_number(self, msg_lower: str) -> Optional[int]:
        """Extrae el número del item que el usuario quiere ver."""
        patterns = [
            r'(?:detalle|detalles|info)\s+(?:de\s+)?(?:la|el)\s+(\d+)',
            r'(?:la|el)\s+(\d+)\b',
            r'(?:número|num|#)\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, msg_lower)
            if match:
                return int(match.group(1))
        return None
    
    def _format_today_emission_detail(self, emission) -> str:
        """Formatea el detalle de una emisión de hoy."""
        tipo = "Factura" if emission.document_type == "01" else "Boleta"
        tipo_emoji = "📄" if emission.document_type == "01" else "🧾"
        symbol = "S/" if emission.currency == "PEN" else "$"
        
        hora = emission.timestamp.strftime("%H:%M") if emission.timestamp else ""
        fecha = emission.timestamp.strftime("%Y-%m-%d") if emission.timestamp else "Hoy"
        
        return f"""{tipo_emoji} **Detalle de {tipo}**

📋 **Número:** {emission.serie_numero}
📅 **Fecha:** {fecha} {hora}
👤 **Cliente:** {emission.client_id}
📦 **Items:** {emission.items_count} producto(s)
💰 **Total:** {symbol}{emission.total:.2f}
📥 **PDF:** {emission.pdf_url if emission.pdf_url else 'No disponible'}

¿Necesitas algo más?"""
    
    def _get_history_detail(self, index: int, session: UserSession) -> str:
        """Obtiene el detalle de un elemento del historial."""
        history = session.context.history
        
        if not history:
            return "No tienes historial."
        
        actual_index = index - 1
        
        if actual_index < 0 or actual_index >= len(history):
            return f"No encontré la emisión #{index}."
        
        h = history[actual_index]
        
        # Mantener contexto de historial
        session.set_context("history")
        
        tipo = "Factura" if h.get('tdocod') == "01" else "Boleta"
        fecha = h.get('ccafem', '')[:10] if h.get('ccafem') else 'Sin fecha'
        cliente = h.get('ccanom', 'Sin nombre')
        doc_cliente = h.get('ccandi', '')
        tipo_doc = "RUC" if h.get('tdicod') == "6" else "DNI"
        
        descripcion = h.get('cdedes', 'Sin descripción')
        cantidad = h.get('cdecan', '1')
        try:
            cantidad = f"{float(cantidad):.0f}"
        except:
            pass
        
        precio_unit = h.get('cdevun', '0')
        igv = h.get('cdeigv', '0')
        total = h.get('cdevve', '0')
        
        try:
            precio_unit = f"{float(precio_unit):.2f}"
            igv = f"{float(igv):.2f}"
            total_f = float(total)
            igv_f = float(igv)
            subtotal = f"{total_f - igv_f:.2f}"
            total = f"{total_f:.2f}"
        except:
            subtotal = "0.00"
        
        serie = h.get('cdaser', '')
        numero = h.get('cdanum', '')
        serie_numero = f"{serie}-{numero}" if serie and numero else "Sin serie"
        
        return f"""📋 **Detalle de {tipo} #{index}**

📅 **Fecha:** {fecha}
📄 **Número:** {serie_numero}

👤 **Cliente:** {cliente}
   {tipo_doc}: {doc_cliente}

📦 **Detalle:**
   {cantidad}x {descripcion}
   Precio unit: S/{precio_unit}

💰 **Totales:**
   Subtotal: S/{subtotal}
   IGV: S/{igv}
   **Total: S/{total}**

💡 Escribe otro número para ver otra emisión."""
    
    def _list_products(self, session: UserSession, msg_lower: str) -> str:
        """Lista los productos."""
        products = session.context.products
        
        if not products:
            return "📦 No tienes productos. Puedes emitir indicando los productos directamente."
        
        search_term = self._extract_search_term(msg_lower)
        if search_term:
            return self._search_products(search_term, session)
        
        # Establecer contexto
        session.set_context("products")
        
        total = len(products)
        showing = min(15, total)
        
        response = f"📦 **Tus productos** ({showing} de {total}):\n\n"
        
        for i, p in enumerate(products[:15], 1):
            nombre = p.get('pronom', 'Sin nombre')
            if len(nombre) > 50:
                nombre = nombre[:47] + "..."
            
            precio = p.get('provun', '0')
            try:
                precio = f"{float(precio):.2f}"
            except:
                pass
            
            response += f"{i}. {nombre}"
            if precio and precio != "0.00":
                response += f" - S/{precio}"
            response += "\n"
        
        if total > 15:
            response += f"\n... y {total - 15} más."
        
        response += "\n\n💡 Escribe un número (1-15) o busca: \"busca laptop\""
        
        return response
    
    def _list_history(self, session: UserSession) -> str:
        """Lista el historial."""
        history = session.context.history
        today = session.session_emissions
        
        # Establecer contexto
        session.set_context("history")
        
        response = f"📊 **Tu historial, {session.user_name}**\n\n"
        
        if today:
            response += f"📅 **Hoy** ({len(today)}):\n"
            for i, e in enumerate(today, 1):
                tipo = "📄" if e.document_type == "01" else "🧾"
                response += f"   {i}. {tipo} {e.serie_numero}: S/{e.total:.2f}\n"
            response += "\n"
        
        if history:
            response += f"📋 **Últimas emisiones** ({min(10, len(history))}):\n\n"
            for i, h in enumerate(history[:10], 1):
                tipo = "Factura" if h.get('tdocod') == "01" else "Boleta"
                cliente = h.get('ccanom', 'Sin nombre')
                if len(cliente) > 25:
                    cliente = cliente[:22] + "..."
                
                fecha = h.get('ccafem', '')[:10] if h.get('ccafem') else ''
                total = h.get('cdevve', '0')
                try:
                    total = f"{float(total):.2f}"
                except:
                    pass
                
                response += f"{i}. {tipo}\n"
                response += f"   👤 {cliente}\n"
                response += f"   💰 S/{total} | 📅 {fecha}\n\n"
            
            response += "💡 Escribe un número para ver detalle (ej: \"5\")"
        else:
            response += "No tienes emisiones previas."
        
        return response
    
    def _explain_invoice_difference(self) -> str:
        return """📋 **Factura vs Boleta**

📄 **FACTURA**
• RUC (11 dígitos)
• Deduce IGV
• Para empresas

🧾 **BOLETA**
• DNI o RUC
• NO deduce IGV
• Para personas

¿Te ayudo a emitir?"""
    
    def _handle_general_question(self, message: str, session: UserSession) -> str:
        msg_lower = message.lower()
        
        if 'diferencia' in msg_lower:
            return self._explain_invoice_difference()
        
        if 'igv' in msg_lower:
            return """📋 **IGV** = 18%

• Se incluye en el precio
• Facturas permiten deducirlo
• Boletas NO

¿Algo más?"""
        
        if any(w in msg_lower for w in ['cómo emitir', 'como emitir']):
            return """📋 **Cómo emitir:**

1️⃣ Tipo (Factura/Boleta)
2️⃣ DNI o RUC
3️⃣ Productos con precio

💡 Ejemplo: "Boleta DNI 12345678, 2 camisas a 50"

¿Empezamos?"""
        
        return self._query_llm(message, IntentType.GENERAL_QUESTION, session)
    
    def _query_llm(self, message: str, intent: IntentType, session: UserSession) -> str:
        ctx_type = {
            IntentType.QUERY_PRODUCTS: "products",
            IntentType.QUERY_CLIENTS: "clients", 
            IntentType.QUERY_HISTORY: "history"
        }.get(intent, "general")
        
        rag_ctx = build_rag_context({
            "products": session.context.products[:20] if session.context.products else [],
            "clients": session.context.clients[:20] if session.context.clients else [],
            "history": session.context.history[:10] if session.context.history else []
        }, ctx_type)
        
        conversation = "\n".join([
            f"{'Usuario' if m.role == 'user' else 'Jack'}: {m.content[:200]}"
            for m in session.messages[-6:]
        ])
        
        prompt = f"""{SYSTEM_PROMPT}

Usuario: {session.user_name}
Contexto: {rag_ctx}
Conversación: {conversation}
Mensaje: {message}

Responde brevemente. NO muestres menú.

Respuesta:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"¿En qué te ayudo, {session.user_name}?"
    
    def handle_greeting(self, session: UserSession) -> str:
        name = session.user_name or "amigo"
        
        # Limpiar contexto en saludo
        session.clear_context()
        
        if session.session_emissions:
            total_hoy = sum(e.total for e in session.session_emissions)
            count = len(session.session_emissions)
            
            emisiones = [f"  • {'📄' if e.document_type == '01' else '🧾'} {e.serie_numero}: S/{e.total:.2f}" 
                        for e in session.session_emissions]
            
            return f"""¡Hola {name}! 👋

📊 **Hoy** ({count}):
{chr(10).join(emisiones)}

💰 Total: S/{total_hoy:.2f}

¿Qué necesitas?"""
        
        products = len(session.context.products) if session.context.products else 0
        
        return f"""¡Hola {name}! 👋

📄 Factura | 🧾 Boleta | 📦 Productos ({products}) | 📊 Historial"""


_agent: Optional[ConversationAgent] = None

def get_conversation_agent() -> ConversationAgent:
    global _agent
    if _agent is None:
        _agent = ConversationAgent()
    return _agent





