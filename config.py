import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
# Esto permite que las variables en .env estén disponibles como variables de entorno
load_dotenv()

# Obtener la ruta base del proyecto
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Clase de configuración principal que contiene todas las configuraciones
    de la aplicación. Usa variables de entorno para valores sensibles.
    """
    
    # Configuración básica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-super-secreta-cambiar-en-produccion'
    
    # Configuración de la base de datos
    # En desarrollo usa SQLite, en producción Railway puede proveer PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{os.path.join(basedir, 'instance', 'chocolates.db')}"
    
    # Desactivar el seguimiento de modificaciones para mejorar el rendimiento
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)  # Las sesiones duran 2 horas
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'  # HTTPS en producción
    SESSION_COOKIE_HTTPONLY = True  # Prevenir acceso a cookies desde JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protección CSRF
    
    # Configuración de WhatsApp
    WHATSAPP_PHONE = os.environ.get('WHATSAPP_PHONE', '+5355059350')
    CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY', '5195222')
    
    # Información del negocio
    BUSINESS_NAME = os.environ.get('APP_NAME', 'Chocolates ByB')
    CURRENCY = os.environ.get('CURRENCY', 'CUP')
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Havana')
    
    # Redes sociales
    FACEBOOK_URL = os.environ.get('FACEBOOK_URL', 'https://facebook.com/ChocolatesBnb')
    INSTAGRAM_URL = os.environ.get('INSTAGRAM_URL', 'https://instagram.com/chocolates_byb')
    
    # Configuración de pedidos
    INITIAL_ORDER_NUMBER = int(os.environ.get('INITIAL_ORDER_NUMBER', '1'))
    MAX_ORDERS_PER_DAY = int(os.environ.get('MAX_ORDERS_PER_DAY', '100'))
    
    # Horarios de entrega disponibles
    DELIVERY_TIME_SLOTS = [
        ('8:00-12:00', 'Mañana (8:00 AM - 12:00 PM)'),
        ('12:00-17:00', 'Tarde (12:00 PM - 5:00 PM)'),
        ('17:00-21:00', 'Noche (5:00 PM - 9:00 PM)')
    ]
    
    # Tipos de chocolate disponibles
    CHOCOLATE_TYPES = [
        ('oscuro', 'Chocolate Oscuro 🍫'),
        ('leche', 'Chocolate con Leche 🤎'),
        ('blanco', 'Chocolate Blanco 🤍')
    ]
    
    # Tamaños disponibles
    PRODUCT_SIZES = [
        ('pequeno', 'Pequeño (115g)', 950),
        ('grande', 'Grande (230g)', 1900)
    ]
    
    # Extras disponibles
    EXTRAS = [
        ('bolsa_regalo', 'Bolsa de Regalo ✨', 200),
        ('tarjeta', 'Tarjeta Personalizada 💌', 150)
    ]
    
    # Diccionario completo de costos de mensajería por zona
    DELIVERY_COSTS = {
        "Habana del Este": {"todas": "NO"},
        "Alamar": {"todas": "NO"},
        "Cotorro": {"todas": "NO"},
        "Regla": {"todas": "NO"},
        
        "Guanabacoa": {
            "Semáforo Guanabacoa": 1350,
            "Habana Nueva": 1350,
            "Azotea": 1350,
            "De Beche": 1450,
            "Guanabacoa": 1450,
            "Nalón": 1500,
            "Chibás": 1450,
            "La Lima": 1550,
            "Naranjo": 1500,
            "La Hata": 1750,
            "Gisela": 1450,
            "El Roble": 1500,
            "Villa María": 1550,
            "Alturas de Villa María": 1550,
            "Cruz Verde": 1400,
            "Santa Fé": 2150,
            "La Yuca": 1150,
            "Los Mangos": 1750,
            "Barreras": "NO",
            "La Gallega": "NO",
            "Minas": "NO",
            "Bacuranao": "NO",
            "Peñalver": "NO",
            "Arango": "NO",
            "El Alecrín": "NO"
        },
        
        "San Miguel": {
            "Luyanó Moderno": 1200,
            "Afán": 1200,
            "La Corea": 1250,
            "Monterrey": 1100,
            "Mirta": 1350,
            "El Diezmero": 1350,
            "San Francisco de Paula": 1350,
            "San Juan de los Pinos (La Cuevita)": 1200,
            "Vista Hermosa": 1250,
            "Jacomino": 1100,
            "Barrio Obrero": 1100,
            "Ciudamar": 1150,
            "El Lucero": 1050,
            "Juanelo": 1100,
            "California": 1150,
            "Martin Pérez": 1200,
            "Rocafort": 1150,
            "La Cumbre": 1150,
            "Las Palmas": 1300,
            "Dolores": 1100,
            "Veracruz": 1150,
            "María Luisa": 1200,
            "San Matías": 1150,
            "Tejas": 1150,
            "Prosperidad": 1400,
            "Reboredo": 1450,
            "La Rosita": 1250,
            "Villa Alegre": 1200,
            "Siboney": 1450,
            "Encanto": 1300,
            "San Pedro": 1350,
            "Alturas de Luyanó": 1150,
            "Las Palmas": 1250,
            "Virgen del Camino": 1050,
            "Bella Vista": 1400,
            "Carolina": 1200
        },
        
        "Marianao": {
            "Todo": 500,
            "CUJAE": 600
        },
        
        "Playa": {
            "Almendares": 500,
            "Buena Vista": 500,
            "Querejeta": 500,
            "Jaimanitas": 500,
            "Flores": 500,
            "Náutico": 500,
            "Siboney": 500,
            "Atabey": 500,
            "Miramar": 550,
            "Kholy": 550,
            "La Ceiba": 550,
            "Santa Fé": 600
        },
        
        "La Lisa": {
            "La Lisa": 500,
            "San Agustín": 500,
            "Arroyo Arenas": 550,
            "El Cano": 700,
            "XX Aniversario": 800,
            "Valle Grande": 800,
            "Punta Brava": 900,
            "Guatao": 1000
        },
        
        "Plaza": {
            "Vedado": 750,
            "Nuevo Vedado": 750
        },
        
        "Centro Habana": {
            "Todo": 900
        },
        
        "Habana Vieja": {
            "Todo": 950
        },
        
        "Boyeros": {
            "Altahabana": 700,
            "El Chico": 850,
            "Wajay": 1050,
            "Fontanar": 1100,
            "Abel Santamaría": 1100,
            "Río Verde": 1050,
            "1ro de Mayo": 1100,
            "Baluarte": 1100,
            "Mazorra": 1200,
            "Calabazar": 1300,
            "Panamerican": 1050,
            "Lutgardita": 1050,
            "Santiago de Las Vegas": 1450,
            "Mulgoba": 1350,
            "Boyeros": 1300,
            "Nuevo Santiago": 1550
        },
        
        "Cerro": {
            "Martí": 750,
            "Ciudad Deportiva": 750,
            "Palatino": 800,
            "Casino Deportivo": 800,
            "Cerro": 950,
            "El Canal": 900,
            "Villanueva": 950,
            "Latinoamericano": 950,
            "Atarés": 950
        },
        
        "10 de Octubre": {
            "Sevillano": 950,
            "Mónaco": 950,
            "La Víbora": 900,
            "Santos Suárez": 900,
            "Acosta": 950,
            "Luyanó": 1000,
            "Lawton": 1000,
            "Vista Alegre": 1100
        },
        
        "Arroyo Naranjo": {
            "Los Pinos": 850,
            "Aldabó": 800,
            "Poey": 900,
            "Víbora Park": 1000,
            "Capri": 950,
            "Vieja Linda": 900,
            "Santa Amalia": 950,
            "La Palma": 950,
            "Mantilla": 1000,
            "Párraga": 1000,
            "La Solita": 1000,
            "Eléctrico": 1300,
            "Guinera": 1050
        }
    }
    
    # Configuración de comisiones (porcentajes)
    COMISION_GESTOR = 0.15  # 15% para gestores
    COMISION_MENSAJERO = 0.10  # 10% para mensajeros
    COMISION_ELABORADOR = 0.20  # 20% para elaboradores
    COMISION_INVERSIONISTA = 0.25  # 25% para inversionistas
    
    # Margen de ganancia del negocio
    MARGEN_NEGOCIO = 0.30  # 30% de ganancia para el negocio
    
    # Configuración de la aplicación
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Límite de 16MB para uploads
    UPLOAD_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
    
    # Configuración para desarrollo/producción
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Método para inicializar configuraciones adicionales si es necesario"""
        pass

class DevelopmentConfig(Config):
    """Configuración específica para desarrollo"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Configuración específica para producción"""
    DEBUG = False
    # En producción, Railway puede cambiar el formato de DATABASE_URL
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Railway a veces usa postgres:// en lugar de postgresql://
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            cls.SQLALCHEMY_DATABASE_URI = database_url

# Diccionario para seleccionar la configuración según el entorno
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
