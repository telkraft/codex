"""
config.py
=========

RAG-Stack API konfigürasyon modülü.

Tüm environment değişkenleri ve sabit ayarlar burada merkezi olarak yönetilir.

🆕 v0.5.0: Çoklu LLM Provider desteği
    - Local (Ollama)
    - Groq Cloud
    - OpenRouter
    - Google AI Studio (Gemini)
    - Cerebras
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# ============================================================================
# ENV LOAD
# ============================================================================

load_dotenv()

# ============================================================================
# BASIC SETTINGS
# ============================================================================

ENV = os.getenv("ENV", "development").lower()
DEBUG = ENV in ("dev", "development")

# ============================================================================
# LRS (MONGO) CONFIG
# ============================================================================

LRS_MONGO_HOST = os.getenv("LRS_MONGO_HOST", "lrs-app")
LRS_MONGO_PORT = int(os.getenv("LRS_MONGO_PORT", 27017))
LRS_MONGO_DB = os.getenv("LRS_MONGO_DB") or os.getenv("LRS_MONGO_DB_NAME", "learninglocker")
LRS_MONGO_COLLECTION = os.getenv("LRS_MONGO_COLLECTION", "statements")

mongo_client = MongoClient(f"mongodb://{LRS_MONGO_HOST}:{LRS_MONGO_PORT}")
lrs_db = mongo_client[LRS_MONGO_DB]
lrs_statements = lrs_db[LRS_MONGO_COLLECTION]

# ============================================================================
# QDRANT CONFIG
# ============================================================================

QDRANT_HOST = os.getenv("QDRANT_HOST", "rag-qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

qdrant_client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)

# ============================================================================
# EMBEDDING MODEL
# ============================================================================

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# ============================================================================
# OLLAMA (LOCAL LLM) CONFIG
# ============================================================================

RAW_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "llm-ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")

if RAW_OLLAMA_HOST.startswith("http://") or RAW_OLLAMA_HOST.startswith("https://"):
    OLLAMA_HOST = RAW_OLLAMA_HOST.rstrip("/")
else:
    OLLAMA_HOST = f"http://{RAW_OLLAMA_HOST}:{OLLAMA_PORT}"

LLM_MODEL_NAME = os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_NAME", "gemma2:2b")

# ============================================================================
# 🆕 LLM PROVIDER API KEYS
# ============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# ============================================================================
# 🆕 LLM PROVIDER ENDPOINTS
# ============================================================================

GROQ_API_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
GOOGLE_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
CEREBRAS_API_BASE = "https://api.cerebras.ai/v1"
MISTRAL_API_BASE = "https://api.mistral.ai/v1"

# ============================================================================
# DEFAULT LLM SETTINGS
# ============================================================================

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "local")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemma2:2b")
DEFAULT_LLM_ROLE = os.getenv("DEFAULT_LLM_ROLE", "servis_analisti")
DEFAULT_LLM_BEHAVIOR = os.getenv("DEFAULT_LLM_BEHAVIOR", "balanced")

# ============================================================================
# 🆕 PROVIDER MODEL CATALOGS
# ============================================================================

PROVIDER_MODELS = {
    "groq": [
        {"value": "llama-3.3-70b-versatile", "label": "Llama 3.3 (70B) • Güçlü", "description": "En popüler"},
        {"value": "llama-3.1-8b-instant", "label": "Llama 3.1 (8B) • Ultra Hızlı", "description": "Anlık yanıt"},
        {"value": "qwen/qwen3-32b", "label": "Qwen 3 (32B) • Çok Dilli", "description": "Türkçe iyi"},
        {"value": "moonshotai/kimi-k2-instruct", "label": "Kimi K2 • Yeni", "description": "Moonshot AI"},
        # {"value": "openai/gpt-oss-120b", "label": "GPT-OSS (120B) • Dev", "description": "OpenAI açık"},
        {"value": "openai/gpt-oss-20b", "label": "GPT-OSS (20B) • Orta", "description": "Dengeli"},
        {"value": "groq/compound", "label": "Compound • Groq Native", "description": "Groq'un modeli"},
        # {"value": "allam-2-7b", "label": "ALLaM 2 (7B) • Arapça", "description": "Arap dili uzmanı"},
    ],
    "openrouter": [
        # Anthropic
        # {"value": "anthropic/claude-sonnet-4", "label": "Claude Sonnet 4 • Güncel", "description": "Dengeli, hızlı"},
        # {"value": "anthropic/claude-sonnet-4.5", "label": "Claude Sonnet 4.5 • En Yeni", "description": "En güncel"},
        # {"value": "anthropic/claude-3.5-sonnet", "label": "Claude 3.5 Sonnet • Popüler", "description": "Stabil"},
        {"value": "anthropic/claude-3.5-haiku", "label": "Claude 3.5 Haiku • Hızlı", "description": "Ekonomik"},
        # OpenAI
        # {"value": "openai/gpt-4o", "label": "GPT-4o • Multimodal", "description": "OpenAI flagship"},
        {"value": "openai/gpt-4o-mini", "label": "GPT-4o Mini • Ekonomik", "description": "Hızlı, ucuz"},
        {"value": "openai/o3-mini", "label": "O3 Mini • Reasoning", "description": "Muhakeme"},
        # Google
        {"value": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash", "description": "Google via OR"},
        # {"value": "google/gemini-2.5-pro", "label": "Gemini 2.5 Pro", "description": "Google güçlü"},
        # Meta
        {"value": "meta-llama/llama-3.3-70b-instruct", "label": "Llama 3.3 (70B)", "description": "Açık kaynak"},
        {"value": "meta-llama/llama-4-maverick", "label": "Llama 4 Maverick • Yeni", "description": "En güncel"},
        # DeepSeek
        {"value": "deepseek/deepseek-chat", "label": "DeepSeek Chat • Ucuz", "description": "Çin, ekonomik"},
        {"value": "deepseek/deepseek-r1", "label": "DeepSeek R1 • Reasoning", "description": "Muhakeme"},
        # Qwen
        {"value": "qwen/qwq-32b", "label": "QwQ (32B) • Reasoning", "description": "Qwen muhakeme"},
        # {"value": "qwen/qwen-max", "label": "Qwen Max • En Güçlü", "description": "Alibaba flagship"},
        # # Mistral
        # {"value": "mistralai/mistral-large-2411", "label": "Mistral Large", "description": "Avrupa lideri"},
    ],
    "google": [
        {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash • En Yeni", "description": "Hızlı, güncel"},
        # {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro • En Güçlü", "description": "En akıllı"},
        # {"value": "gemini-2.0-flash", "label": "Gemini 2.0 Flash • Stabil", "description": "Dengeli"},
        # {"value": "gemini-2.0-flash-lite", "label": "Gemini 2.0 Flash Lite • Hafif", "description": "Ultra hızlı"},
        # {"value": "gemma-3-27b-it", "label": "Gemma 3 (27B) • Açık", "description": "Güçlü, açık kaynak"},
        # {"value": "gemma-3-12b-it", "label": "Gemma 3 (12B) • Orta", "description": "Dengeli"},
    ],
    "cerebras": [
        {"value": "llama-3.3-70b", "label": "Llama 3.3 (70B) • Güçlü", "description": "450 token/sn"},
        {"value": "llama3.1-8b", "label": "Llama 3.1 (8B) • Ultra Hızlı", "description": "2100 token/sn"},
        {"value": "qwen-3-235b-a22b-instruct-2507", "label": "Qwen 3 (235B) • Dev", "description": "MoE, çok güçlü"},
        {"value": "qwen-3-32b", "label": "Qwen 3 (32B) • Dengeli", "description": "Çok dilli"},
        {"value": "gpt-oss-120b", "label": "GPT-OSS (120B) • Açık", "description": "OpenAI açık kaynak"},
        # {"value": "zai-glm-4.6", "label": "GLM 4.6 • Çin", "description": "Zhipu AI"},
    ],
    "mistral": [
        {"value": "mistral-large-latest", "label": "Mistral Large • Flagship", "description": "En güçlü"},
        {"value": "mistral-medium-latest", "label": "Mistral Medium • Dengeli", "description": "Performans/maliyet"},
        {"value": "mistral-small-latest", "label": "Mistral Small • Hızlı", "description": "Ekonomik"},
        {"value": "codestral-latest", "label": "Codestral • Kod Uzmanı", "description": "Kod üretimi"},
        {"value": "open-mistral-nemo", "label": "Mistral Nemo • Açık", "description": "12B, açık kaynak"},
        {"value": "ministral-8b-latest", "label": "Ministral (8B) • Kompakt", "description": "Edge için"},
        {"value": "pixtral-large-latest", "label": "Pixtral Large • Görsel", "description": "Multimodal"},
        {"value": "devstral-latest", "label": "Devstral • Geliştirici", "description": "Kod + reasoning"},
    ],
    "local": [
        {"value": "gemma2:2b", "label": "Gemma 2 (2B) • Ultra Hafif", "description": "En hızlı yanıt"},
        {"value": "qwen2.5:0.5b", "label": "Qwen 2.5 (0.5B) • Minimal", "description": "Çok hafif"},
        {"value": "llama3.2:3b", "label": "Llama 3.2 (3B) • Hızlı Yanıt", "description": "Dengeli hız"},
        {"value": "llama3.1:8b", "label": "Llama 3.1 (8B) • Genel Amaçlı", "description": "Önerilen"},
        {"value": "RefinedNeuro/Turkcell-LLM-7b-v1:latest", "label": "Turkcell (7B) • Türkçe Uzman", "description": "Türkçe optimize"},
        {"value": "RefinedNeuro/RN_TR_R2:latest", "label": "TR-R2 (8B) • Türkçe Muhakeme", "description": "Gelişmiş Türkçe"},
        {"value": "aya-expanse:8b", "label": "Aya (8B) • Çok Dilli", "description": "Çok dil desteği"},
    ],
}

# ============================================================================
# PROVIDER DEFAULT MODELS
# ============================================================================

PROVIDER_DEFAULTS = {
    "local": "gemma2:2b",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "anthropic/claude-3.5-haiku",
    "google": "gemini-2.5-flash",
    "cerebras": "llama-3.3-70b",
    "mistral": "mistral-large-latest",
}

# ============================================================================
# PROVIDER METADATA
# ============================================================================

PROVIDERS_CONFIG = {
    "local": {
        "id": "local",
        "name": "Local (Ollama)",
        "icon": "🏠",
        "description": "Yerel sunucuda çalışan Ollama modelleri",
        "pricing": "Ücretsiz (kendi donanımınız)",
        "latency": "Donanıma bağlı",
    },
    "groq": {
        "id": "groq",
        "name": "Groq Cloud",
        "icon": "⚡",
        "description": "Groq LPU ile ultra hızlı inference",
        "pricing": "Çok düşük maliyet",
        "latency": "~100ms",
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "icon": "🌐",
        "description": "Claude, GPT-4, Gemini ve 200+ model tek API'de",
        "pricing": "Model bazlı (kullandıkça öde)",
        "latency": "Model bazlı",
    },
    "google": {
        "id": "google",
        "name": "Google AI Studio",
        "icon": "🔷",
        "description": "Google Gemini modelleri",
        "pricing": "Ücretsiz tier + kullandıkça öde",
        "latency": "~200ms",
    },
    "cerebras": {
        "id": "cerebras",
        "name": "Cerebras",
        "icon": "🧠",
        "description": "Dünyanın en hızlı AI inference (2100 token/sn)",
        "pricing": "Düşük maliyet",
        "latency": "~50ms",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "icon": "🌀",
        "description": "Avrupa'nın lider AI şirketi, güçlü açık modeller",
        "pricing": "Rekabetçi fiyatlandırma",
        "latency": "~150ms",
    },
}

# ============================================================================
# LLM ROLES
# ============================================================================

LLM_ROLES = [
    {"value": "servis_analisti", "label": "Servis Analisti", "description": "Operasyonel analiz"},
    {"value": "filo_yoneticisi", "label": "Filo Yöneticisi", "description": "Filo yönetimi"},
    {"value": "teknik_uzman", "label": "Teknik Uzman", "description": "Teknik detay"},
    {"value": "musteri_temsilcisi", "label": "Müşteri Temsilcisi", "description": "Müşteri odaklı"},
    {"value": "egitmen", "label": "Eğitmen", "description": "Eğitim amaçlı"},
    {"value": "tedarik_zinciri_uzmani", "label": "Tedarik Zinciri Uzmanı", "description": "Lojistik odaklı"},
    {"value": "cto", "label": "CTO", "description": "Stratejik bakış"},
]

# ============================================================================
# LLM BEHAVIORS
# ============================================================================

LLM_BEHAVIORS = [
    {"value": "balanced", "label": "Analitik Yaklaşım", "description": "Önerilen"},
    {"value": "commentary", "label": "Yorumlayıcı", "description": "Açıklayıcı"},
    {"value": "predictive", "label": "Hipotez Üreten", "description": "Senaryo tabanlı"},
    {"value": "report", "label": "Rapor Oluşturan", "description": "Yapılandırılmış"},
]

# ============================================================================
# API / GENERAL SETTINGS
# ============================================================================

MAX_EXAMPLE_STATEMENTS = int(os.getenv("MAX_EXAMPLE_STATEMENTS", 5))
DEFAULT_TIMEZONE = "Europe/Istanbul"

# ============================================================================
# LRS / LLM LIMIT SETTINGS
# ============================================================================

STATS_TABLE_LIMIT = int(os.getenv("STATS_TABLE_LIMIT", 200))
DOMAIN_STATS_LIMIT = int(os.getenv("DOMAIN_STATS_LIMIT", 200))
LLM_CONTEXT_MAX_ROWS = int(os.getenv("LLM_CONTEXT_MAX_ROWS", 20))

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    # Basic
    "ENV",
    "DEBUG",
    # MongoDB
    "lrs_statements",
    "lrs_db",
    "mongo_client",
    # Qdrant
    "qdrant_client",
    # Embedding
    "embedding_model",
    "EMBEDDING_MODEL_NAME",
    # Ollama
    "OLLAMA_HOST",
    "LLM_MODEL_NAME",
    # Limits
    "MAX_EXAMPLE_STATEMENTS",
    "DEFAULT_TIMEZONE",
    "STATS_TABLE_LIMIT",
    "DOMAIN_STATS_LIMIT",
    "LLM_CONTEXT_MAX_ROWS",
    # 🆕 LLM Provider API Keys
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY",
    "CEREBRAS_API_KEY",
    "MISTRAL_API_KEY",
    # 🆕 LLM Provider Endpoints
    "GROQ_API_BASE",
    "OPENROUTER_API_BASE",
    "GOOGLE_API_BASE",
    "CEREBRAS_API_BASE",
    "MISTRAL_API_BASE",
    # 🆕 LLM Provider Config
    "DEFAULT_LLM_PROVIDER",
    "DEFAULT_LLM_MODEL",
    "DEFAULT_LLM_ROLE",
    "DEFAULT_LLM_BEHAVIOR",
    "PROVIDER_MODELS",
    "PROVIDER_DEFAULTS",
    "PROVIDERS_CONFIG",
    "LLM_ROLES",
    "LLM_BEHAVIORS",
]
