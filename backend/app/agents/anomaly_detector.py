"""
Anomaly Detector - Detecta anomalías en emisiones.
"""
import logging
from typing import List
from app.models.schemas import UserSession

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def detect_anomalies(self, session: UserSession) -> List[str]:
        anomalies = []
        emission = session.emission_data
        
        if not emission.items:
            return anomalies
        
        products = session.context.products
        history = session.context.history
        
        # 1. Verificar precios vs catálogo
        if products:
            product_prices = {p.get('pronom', '').lower(): float(p.get('provun', 0)) for p in products}
            
            for item in emission.items:
                item_name = item.descripcion.lower()
                item_price = float(item.precio)
                
                for name, catalog_price in product_prices.items():
                    if item_name in name or name in item_name:
                        if catalog_price > 0:
                            diff = abs(item_price - catalog_price) / catalog_price
                            if diff > 0.5:  # >50% diferencia
                                anomalies.append(
                                    f"'{item.descripcion}' a S/{item_price:.2f} difiere del catálogo (S/{catalog_price:.2f})"
                                )
                        break
        
        # 2. Verificar cantidades altas
        for item in emission.items:
            try:
                cant = int(float(item.cantidad))
                if cant >= 100:
                    anomalies.append(f"Cantidad alta: {cant} unidades de '{item.descripcion}'")
            except:
                pass
        
        # 3. Verificar monto total vs historial
        if history:
            total = emission.calculate_total()
            try:
                amounts = [float(h.get('cdevve', 0)) for h in history if h.get('cdevve')]
                if amounts:
                    avg = sum(amounts) / len(amounts)
                    if total > avg * 10:
                        anomalies.append(f"Monto S/{total:.2f} es {total/avg:.1f}x tu promedio (S/{avg:.2f})")
            except:
                pass
        
        return anomalies


_detector = None

def get_anomaly_detector():
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
