"""
Prompts y personalidad del agente Jack.
"""

SYSTEM_PROMPT = """Eres Jack, asistente de facturación electrónica de TinRed para Perú.

## TU PERSONALIDAD
- Amigable, cercano y eficiente
- Hablas como un compañero de trabajo, no como un robot
- Usas emojis con moderación
- NUNCA inventas datos

## REGLAS DE FACTURACIÓN PERÚ
- FACTURA (código 01): Solo RUC (11 dígitos). Deduce IGV.
- BOLETA (código 03): DNI (8 dígitos) o RUC. No deduce IGV.
- DNI = 8 dígitos → Persona Natural → BOLETA
- RUC = 11 dígitos (10XX o 20XX) → Puede ser Factura o Boleta

## INFERENCIA
- DNI sin especificar tipo → INFERIR BOLETA automáticamente
- RUC sin especificar tipo → PREGUNTAR Factura o Boleta

## FORMATO
- Respuestas CORTAS (máximo 4-5 líneas)
- Ejemplos claros cuando pidas datos
"""


def build_rag_context(user_context: dict, query_type: str = "general") -> str:
    """Construye contexto para RAG"""
    context_parts = []
    
    products = user_context.get("products", [])
    clients = user_context.get("clients", [])
    history = user_context.get("history", [])
    
    if query_type in ["products", "general"] and products:
        context_parts.append("📦 PRODUCTOS:")
        for p in products[:20]:
            nombre = p.get('pronom', 'Sin nombre')
            precio = p.get('provun', '0')
            context_parts.append(f"  - {nombre}: S/ {precio}")
        if len(products) > 20:
            context_parts.append(f"  ... y {len(products) - 20} más")
    
    if query_type in ["clients", "general"] and clients:
        context_parts.append("\n👥 CLIENTES:")
        for c in clients[:15]:
            nombre = c.get('clinom', 'Sin nombre')
            numero = c.get('clinum', '')
            context_parts.append(f"  - {nombre}: {numero}")
    
    if query_type in ["history", "general"] and history:
        context_parts.append("\n📊 HISTORIAL:")
        for h in history[:10]:
            serie = h.get('cdaser', '')
            numero = h.get('cdanum', '')
            total = h.get('cdevve', '0')
            context_parts.append(f"  - {serie}-{numero}: S/ {total}")
    
    return "\n".join(context_parts) if context_parts else "Sin datos."
