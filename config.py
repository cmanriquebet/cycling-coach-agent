# ⚙️ CONFIGURACIÓN DEL AGENTE
# Lee desde GitHub Secrets (SEGURO)

import os

# ============================================================================
# CREDENCIALES GARMIN CONNECT (desde Secrets)
# ============================================================================

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "carlotronico@hotmail.com")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")

# ============================================================================
# WHATSAPP (desde Secrets)
# ============================================================================

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "+34607961337")

# ============================================================================
# GOOGLE SHEETS (desde Secrets)
# ============================================================================

GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")

# ============================================================================
# TU PERFIL CICLISTA
# ============================================================================

FTP = 252  # Watts
PESO = 71  # kg
HR_MAX = 187  # Frecuencia cardíaca máxima

# Tipo: "CARRETERA", "MTB", "MIXTO"
TIPO_CICLISTA = "MIXTO"

# ============================================================================
# NO EDITES NADA MÁS ABAJO
# ============================================================================

DEBUG = False
LOG_LEVEL = "INFO"
