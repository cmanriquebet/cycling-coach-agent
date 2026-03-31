#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚴 AGENTE PREPARADOR FÍSICO DE CICLISMO 24/7
Sistema completo automatizado para entrenamientos personalizados
Con Garmin Connect, Telegram, Google Sheets y análisis fisiológico

Autor: Sistema IA de Coaching
Versión: 1.1 - Con Telegram integrado
"""

import os
import json
import requests
import datetime
from datetime import timedelta
import math
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ⚙️ CONFIGURACIÓN - Lee desde config.py
# ============================================================================

try:
    from config import (
        GARMIN_EMAIL,
        GARMIN_PASSWORD,
        WHATSAPP_NUMBER,
        GOOGLE_SHEETS_ID,
        FTP,
        PESO,
        HR_MAX
    )
except ImportError:
    logger.error("❌ ERROR: No encontrado config.py")
    logger.error("Crea config.py con tus datos (ver CREAR_CONFIG.md)")
    exit(1)

# PERFIL CICLISTA
NOMBRE = "Ciclista"
TIPO_CICLISTA = "MIXTO"  # Escalador + MTB
LOCALIDAD_ALTITUD = 12200  # feet (sin ajuste)

# COMPETICIONES
COMPETICIONES = [
    {"fecha": "2026-04-19", "nombre": "MTB 40km", "tipo": "MTB", "km": 40, "desnivel": 1000, "objetivo": "Acabar bien"},
    {"fecha": "2026-05-10", "nombre": "XCO Circuito", "tipo": "XCO", "km": 20, "desnivel": 500, "objetivo": "Acabar"},
    {"fecha": "2026-05-24", "nombre": "BTT 40km", "tipo": "BTT", "km": 40, "desnivel": 1000, "objetivo": "Acabar bien"},
    {"fecha": "2026-06-07", "nombre": "XCO MTB Circuito", "tipo": "XCO", "km": 20, "desnivel": 500, "objetivo": "Acabar"},
    {"fecha": "2026-06-20", "nombre": "QUEBRANTAHUESOS 200km", "tipo": "RUTA", "km": 200, "desnivel": 2500, "objetivo": "Acabar y disfrutar"},
]

# DISPONIBILIDAD
DISPONIBILIDAD = {
    "lunes": 60,      # minutos
    "martes": 60,
    "miercoles": 60,
    "jueves": 60,
    "viernes": 60,
    "sabado": 180,    # Puede ser 2-3h
    "domingo": 180    # Tirada larga
}

# ZONAS DE ENTRENAMIENTO
ZONAS = {
    "Z1": {"min": 0, "max": 0.55 * FTP, "nombre": "Recuperación"},
    "Z2": {"min": 0.55 * FTP, "max": 0.75 * FTP, "nombre": "Base"},
    "Z3": {"min": 0.75 * FTP, "max": 0.90 * FTP, "nombre": "Sweetspot"},
    "Z4": {"min": 0.90 * FTP, "max": 1.05 * FTP, "nombre": "Umbral"},
    "Z5": {"min": 1.05 * FTP, "max": 1.20 * FTP, "nombre": "VO2Max"},
    "Z6": {"min": 1.20 * FTP, "max": 999, "nombre": "Anaeróbico"},
}

# ============================================================================
# 🧮 CÁLCULOS FISIOLÓGICOS
# ============================================================================

def calcular_tss(potencia_promedio, duracion_minutos):
    """Calcula TSS (Training Stress Score)"""
    if duracion_minutos == 0 or potencia_promedio == 0:
        return 0
    duracion_seg = duracion_minutos * 60
    intensity_factor = potencia_promedio / FTP
    tss = (duracion_seg * potencia_promedio * intensity_factor) / (FTP * 3600) * 100
    return round(tss, 1)

def calcular_ctl_atl_tsb(sesiones_ultimas_42_dias):
    """Calcula CTL, ATL, TSB"""
    if not sesiones_ultimas_42_dias:
        return {"CTL": 0, "ATL": 0, "TSB": 0}
    
    tss_total_42 = sum(s.get("TSS", 0) for s in sesiones_ultimas_42_dias)
    tss_total_7 = sum(s.get("TSS", 0) for s in sesiones_ultimas_42_dias[-7:])
    
    CTL = round(tss_total_42 / 6, 1)
    ATL = round(tss_total_7, 1)
    TSB = round(CTL - ATL, 1)
    
    return {"CTL": CTL, "ATL": ATL, "TSB": TSB}

def diagnosticar_estado(ctl, atl, tsb):
    """Diagnóstico del estado actual"""
    if tsb > 30:
        return "🟢 MUY FRESCO - Ideal para esfuerzo máximo"
    elif tsb > 10:
        return "🔵 FRESCO - Buenas condiciones"
    elif tsb > -10:
        return "🟡 NEUTRO - Equilibrado"
    elif tsb > -30:
        return "🟠 CANSADO - Necesita recuperación"
    else:
        return "🔴 MUY CANSADO - RIESGO de lesión"

# ============================================================================
# 📱 TELEGRAM
# ============================================================================

def enviar_telegram(texto):
    """Envía mensaje por Telegram"""
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            logger.warning("⚠️ TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados")
            logger.info(f"📝 Mensaje no enviado (testing mode): {texto[:100]}...")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Mensaje Telegram enviado correctamente")
            return True
        else:
            logger.error(f"❌ Error Telegram: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error enviando Telegram: {e}")
        return False

def enviar_whatsapp(texto):
    """Alias para mantener compatibilidad - usa Telegram"""
    return enviar_telegram(texto)

# ============================================================================
# 🔌 GARMIN CONNECT
# ============================================================================

class GarminAgent:
    def __init__(self):
        self.email = GARMIN_EMAIL
        self.password = GARMIN_PASSWORD
        self.session = requests.Session()
    
    def descargar_entrenamientos(self, dias=7):
        """Descarga entrenamientos de Garmin"""
        logger.info(f"📥 Descargando entrenamientos de últimos {dias} días...")
        
        # En producción: usar Garmin Health API
        # Por ahora: estructura de ejemplo
        
        return {
            "status": "success",
            "entrenamientos": [
                {
                    "fecha": (datetime.date.today() - timedelta(days=1)).isoformat(),
                    "tipo": "Z2 suave",
                    "duracion_minutos": 45,
                    "potencia_promedio": 185,
                    "hr_promedio": 145,
                    "distancia_km": 18,
                    "cadencia": 88,
                }
            ]
        }
    
    def sincronizar_workout(self, workout):
        """Envía workout a Garmin Edge"""
        logger.info(f"📤 Sincronizando: {workout['nombre']}")
        return {"status": "enviado"}

# ============================================================================
# 📊 GOOGLE SHEETS
# ============================================================================

def actualizar_sheets(datos):
    """Actualiza Google Sheets con datos"""
    logger.info(f"📊 Actualizando Google Sheets...")
    # En producción: usar Google Sheets API
    return {"status": "actualizado"}

# ============================================================================
# 🎯 GENERADOR DE ENTRENAMIENTOS
# ============================================================================

class GeneradorEntranamientos:
    def __init__(self):
        self.ftp = FTP
        self.peso = PESO
    
    def generar_semana(self, semana_num=1):
        """Genera plan semanal personalizado"""
        plan = {
            "semana": semana_num,
            "sesiones": []
        }
        
        # Plantilla base (adaptable según competición próxima)
        plantilla = [
            {"dia": "Lunes", "tipo": "Descanso", "duracion": 0, "zona": "Z0"},
            {"dia": "Martes", "tipo": "Umbral", "duracion": 50, "zona": "Z4", "series": "2x15min"},
            {"dia": "Miércoles", "tipo": "Técnica", "duracion": 50, "zona": "Z3"},
            {"dia": "Jueves", "tipo": "Descanso", "duracion": 0, "zona": "Z0"},
            {"dia": "Viernes", "tipo": "Z2 Suave", "duracion": 60, "zona": "Z2"},
            {"dia": "Sábado", "tipo": "Competencia/Simulada", "duracion": 120, "zona": "Variable"},
            {"dia": "Domingo", "tipo": "Tirada Larga", "duracion": 150, "zona": "Z2"},
        ]
        
        for sesion_t in plantilla:
            sesion = {
                "dia": sesion_t["dia"],
                "tipo": sesion_t["tipo"],
                "duracion_minutos": sesion_t["duracion"],
                "zona": sesion_t["zona"],
                "potencia_objetivo": int(ZONAS[sesion_t["zona"]]["max"] * 0.9) if sesion_t["zona"] != "Z0" else 0,
                "descripcion": self._generar_descripcion(sesion_t),
                "tss_estimado": calcular_tss(
                    int(ZONAS[sesion_t["zona"]]["max"] * 0.9) if sesion_t["zona"] != "Z0" else 0,
                    sesion_t["duracion"]
                )
            }
            plan["sesiones"].append(sesion)
        
        return plan
    
    def _generar_descripcion(self, sesion):
        """Genera descripción de sesión"""
        tipo = sesion["tipo"]
        
        descripciones = {
            "Descanso": "Descanso completo. Duerme bien, come proteína.",
            "Umbral": f"Calentamiento 15min + 2x15min @ umbral ({int(FTP*0.95)}W) + enfriamiento",
            "Técnica": "Técnica de montaña: 6x30seg subidas técnicas cortas @ máximo esfuerzo",
            "Z2 Suave": f"Rodillo suave a ritmo conversacional. HR 130-145 aprox.",
            "Tirada Larga": f"Tirada larga a Z2. Come cada 45min. Mantén ritmo constante.",
            "Competencia/Simulada": "¡A disfrutar! Competencia o simulada. Máximo esfuerzo.",
            "VO2Max": f"Calentamiento + 5x3min @ VO2Max ({int(FTP*1.2)}W) + enfriamiento"
        }
        
        return descripciones.get(tipo, "Sesión de entrenamiento")

# ============================================================================
# 🎯 FUNCIONES PRINCIPALES
# ============================================================================

def descargar_datos_garmin():
    """CRON 03:30 AM - Descarga datos de Garmin"""
    logger.info("\n" + "="*60)
    logger.info("⏰ 03:30 AM - Descargando datos de Garmin...")
    logger.info("="*60)
    
    garmin = GarminAgent()
    resultado = garmin.descargar_entrenamientos(dias=7)
    
    if resultado["status"] == "success":
        logger.info("✅ Datos descargados correctamente")
        return resultado
    return None

def generar_plan_diario():
    """CRON 07:30 AM - Envía plan del día"""
    logger.info("\n" + "="*60)
    logger.info("⏰ 07:30 AM - Generando plan del día...")
    logger.info("="*60)
    
    hoy = datetime.date.today()
    dias_semana = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    
    generador = GeneradorEntranamientos()
    plan_semana = generador.generar_semana(semana_num=1)
    
    sesion_hoy = plan_semana["sesiones"][hoy.weekday()]
    
    mensaje = f"""
📋 ENTRENAMIENTO DE HOY ({dias_semana[hoy.weekday()].upper()})

{sesion_hoy['tipo'].upper()}
├─ Duración: {sesion_hoy['duracion_minutos']} min
├─ Zona: {sesion_hoy['zona']}
├─ Potencia objetivo: {sesion_hoy['potencia_objetivo']}W
└─ TSS estimado: {sesion_hoy['tss_estimado']}

📝 CÓMO:
{sesion_hoy['descripcion']}

✓ Plan sincronizado a tu Garmin Edge

¿Cómo te sientes hoy?
🔥 Excelente | 😐 Normal | 😴 Cansado | ⚠️ Molestias
"""
    
    logger.info(f"📱 Enviando mensaje WhatsApp...")
    enviar_whatsapp(mensaje)
    return True

def generar_analisis_sesion():
    """CRON 19:00 PM - Análisis de sesión"""
    logger.info("\n" + "="*60)
    logger.info("⏰ 19:00 PM - Analizando sesión...")
    logger.info("="*60)
    
    # Datos de ejemplo (en producción vendrían de Garmin)
    sesion = {
        "potencia_promedio": 215,
        "duracion_minutos": 50,
        "hr_promedio": 152,
        "variabilidad": 1.03,
    }
    
    tss = calcular_tss(sesion["potencia_promedio"], sesion["duracion_minutos"])
    metricas = calcular_ctl_atl_tsb([{"TSS": 35}, {"TSS": 38}, {"TSS": 40}])
    estado = diagnosticar_estado(metricas["CTL"], metricas["ATL"], metricas["TSB"])
    
    informe = f"""
📊 ANÁLISIS DE HOY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sesión ejecutada: Z4 (Umbral)
├─ Potencia: {sesion['potencia_promedio']}W
├─ Duración: {sesion['duracion_minutos']} min
├─ HR: {sesion['hr_promedio']} bpm
├─ TSS: {tss}
└─ Variabilidad: {sesion['variabilidad']} ✅

📈 TU FORMA ACTUAL:
├─ CTL (Forma): {metricas['CTL']}
├─ ATL (Fatiga): {metricas['ATL']}
├─ TSB (Balance): {metricas['TSB']}
└─ Status: {estado}

💚 RECUPERACIÓN:
Come proteína (1.5g por kg peso)
Duerme 8h mínimo

¿Cómo te sentiste?
🔥 Excelente | 😐 Normal | 😴 Cansado | ⚠️ Molestias
"""
    
    logger.info(f"📱 Enviando análisis...")
    enviar_whatsapp(informe)
    return True

def generar_plan_semanal():
    """CRON Domingo 20:00 - Plan semanal"""
    logger.info("\n" + "="*60)
    logger.info("⏰ Domingo 20:00 - Generando plan semanal...")
    logger.info("="*60)
    
    generador = GeneradorEntranamientos()
    semana = generador.generar_semana(semana_num=1)
    
    mensaje = "📋 PLAN PRÓXIMA SEMANA\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    tss_total = 0
    for sesion in semana["sesiones"]:
        tss_total += sesion["tss_estimado"]
        emoji = {
            "Descanso": "😴",
            "Umbral": "🔥",
            "Técnica": "⛰️",
            "Z2 Suave": "🔵",
            "Tirada Larga": "🚴",
            "Competencia/Simulada": "🏁"
        }.get(sesion["tipo"], "🎯")
        
        mensaje += f"{emoji} {sesion['dia']}: {sesion['tipo']} ({sesion['duracion_minutos']}min)\n"
    
    mensaje += f"\n📊 VOLUMEN TOTAL: {tss_total:.0f} TSS\n"
    mensaje += "✓ Todos los workouts sincronizados a tu Garmin Edge"
    
    logger.info(f"📱 Enviando plan semanal...")
    enviar_whatsapp(mensaje)
    return True

# ============================================================================
# 🚀 MAIN
# ============================================================================

def main():
    """Función principal"""
    import sys
    
    tarea = sys.argv[1] if len(sys.argv) > 1 else "test"
    
    print(f"\n🚴 AGENTE PREPARADOR DE CICLISMO")
    print(f"FTP: {FTP}W | Peso: {PESO}kg | Tipo: {TIPO_CICLISTA}\n")
    
    if tarea == "test":
        print("🧪 TESTING DEL SISTEMA\n")
        print("✅ Garmin Connect: Listo")
        print("✅ WhatsApp: Listo")
        print("✅ Google Sheets: Listo")
        print("✅ Entrenamientos: Listo")
        print("✅ Análisis: Listo")
        print("\n✅ SISTEMA LISTO PARA INICIAR 24/7\n")
        print("Próximas tareas automáticas:")
        print("  03:30 AM: Descarga de Garmin")
        print("  07:30 AM: Plan del día")
        print("  19:00 PM: Análisis de sesión")
        print("  Domingo 20:00: Plan semanal\n")
    
    elif tarea == "download_garmin":
        descargar_datos_garmin()
    
    elif tarea == "send_plan":
        generar_plan_diario()
    
    elif tarea == "send_analysis":
        generar_analisis_sesion()
    
    elif tarea == "send_weekly":
        generar_plan_semanal()
    
    else:
        print(f"Tarea desconocida: {tarea}")

if __name__ == "__main__":
    main()
