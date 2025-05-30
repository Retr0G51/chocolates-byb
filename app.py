import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
import requests
import csv
import io
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64
from collections import defaultdict
from sqlalchemy import func, extract, and_

app = Flask(__name__)

# Configuration for Railway
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chocolates-byb-2024-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chocolates.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed extensions for images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Fix Postgres URL if needed
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://')

db = SQLAlchemy(app)

# WhatsApp Configuration
WHATSAPP_PHONE = os.environ.get('WHATSAPP_PHONE', '+5355059350')
WHATSAPP_APIKEY = os.environ.get('WHATSAPP_APIKEY', '5195222')

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MODELS
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    tipo = db.Column(db.String(50))  # blanco, con_leche
    tamano = db.Column(db.String(50))  # grande, mediano, pequeno, vulva
    peso = db.Column(db.String(50))  # 230g, 50g, 15g, 25g
    precio = db.Column(db.Float, nullable=False)
    costo = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=100)
    imagen = db.Column(db.String(200))
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

class ZonaEntrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    municipio = db.Column(db.String(100), nullable=False)
    reparto = db.Column(db.String(100), nullable=False)
    precio_mensajeria = db.Column(db.Float, nullable=False)
    disponible = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_orden = db.Column(db.Integer, unique=True)  # 1423, 1424, etc
    fecha_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_entrega = db.Column(db.Date)
    horario_entrega = db.Column(db.String(50))  # manana, tarde, noche
    
    # Cliente info
    cliente_nombre = db.Column(db.String(100))
    cliente_telefono = db.Column(db.String(20))
    cliente_direccion_calle = db.Column(db.Text)  # Calle, numero, entrecalles
    cliente_municipio = db.Column(db.String(100))
    cliente_reparto = db.Column(db.String(100))
    
    # Pedido info
    observaciones = db.Column(db.Text)
    precio_mensajeria = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    total = db.Column(db.Float)
    estado = db.Column(db.String(20), default='pendiente')
    
    # Relationship
    items = db.relationship('ItemPedido', backref='pedido', lazy=True, cascade='all, delete-orphan')
    
    def actualizar_cliente(self):
        """Actualiza o crea un cliente basado en el pedido"""
        cliente = Cliente.query.filter_by(telefono=self.cliente_telefono).first()
        
        if not cliente:
            cliente = Cliente(
                nombre=self.cliente_nombre,
                telefono=self.cliente_telefono,
                direccion_calle=self.cliente_direccion_calle,
                municipio=self.cliente_municipio,
                reparto=self.cliente_reparto,
                fecha_registro=datetime.utcnow(),
                ultimo_pedido=self.fecha_pedido,
                pedidos_completados=1,
                total_gastado=self.total
            )
        else:
            cliente.ultimo_pedido = self.fecha_pedido
            cliente.pedidos_completados += 1
            cliente.total_gastado += self.total
            # Actualizar dirección si ha cambiado
            if self.cliente_direccion_calle:
                cliente.direccion_calle = self.cliente_direccion_calle
            if self.cliente_municipio:
                cliente.municipio = self.cliente_municipio
            if self.cliente_reparto:
                cliente.reparto = self.cliente_reparto
        
        db.session.add(cliente)
        return cliente

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    producto = db.relationship('Producto')
    cantidad = db.Column(db.Integer, default=1)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120))
    direccion_calle = db.Column(db.Text)
    municipio = db.Column(db.String(100))
    reparto = db.Column(db.String(100))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_pedido = db.Column(db.DateTime)
    pedidos_completados = db.Column(db.Integer, default=0)
    total_gastado = db.Column(db.Float, default=0)
    notas = db.Column(db.Text)
    
class MateriaPrima(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    unidad = db.Column(db.String(20))  # kg, g, l, ml, etc.
    stock = db.Column(db.Float, default=0)
    costo_unitario = db.Column(db.Float, default=0)
    proveedor = db.Column(db.String(100))
    fecha_ultima_compra = db.Column(db.DateTime)
    nivel_alerta = db.Column(db.Float)  # Nivel mínimo para alertar
    notas = db.Column(db.Text)

class Receta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    producto = db.relationship('Producto', backref='recetas')
    ingredientes = db.relationship('RecetaIngrediente', backref='receta', cascade='all, delete-orphan')
    costo_total = db.Column(db.Float, default=0)
    rendimiento = db.Column(db.Integer)  # Cuántas unidades produce
    tiempo_preparacion = db.Column(db.Integer)  # minutos
    instrucciones = db.Column(db.Text)

class RecetaIngrediente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receta_id = db.Column(db.Integer, db.ForeignKey('receta.id'), nullable=False)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materia_prima.id'), nullable=False)
    materia_prima = db.relationship('MateriaPrima')
    cantidad = db.Column(db.Float, nullable=False)

# HELPER FUNCTIONS
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_next_order_number():
    last_order = Pedido.query.order_by(Pedido.numero_orden.desc()).first()
    if last_order and last_order.numero_orden:
        return last_order.numero_orden + 1
    return 1  # Starting number

def format_horario(horario):
    horarios = {
        'manana': '8:30 - 11:30 AM',
        'tarde': '2:00 - 5:00 PM',
        'noche': '6:00 - 9:00 PM'
    }
    return horarios.get(horario, horario)

def get_emoji_tipo(tipo):
    emojis = {
        'blanco': '⚪',
        'con_leche': '🟤'
    }
    return emojis.get(tipo, '')

def format_whatsapp_message(pedido):
    # Header
    mensaje = f"🔸 *{pedido.numero_orden} Orden de Factura* 🏷️\n\n"
    
    # Fecha de pedido
    mensaje += f"🗓️ Fecha de pedido: {pedido.fecha_pedido.strftime('%d/%m/%Y')}\n"
    
    # Cliente info
    mensaje += f"👤 Cliente: {pedido.cliente_nombre}\n"
    mensaje += f"📞 Teléfono: {pedido.cliente_telefono}\n"
    mensaje += f"📍 Dirección:\n"
    mensaje += f"   • {pedido.cliente_direccion_calle}\n"
    mensaje += f"   • {pedido.cliente_municipio}\n"
    mensaje += f"   • {pedido.cliente_reparto}\n"
    
    # Entrega
    mensaje += f"🕒 Fecha y hora de entrega: {pedido.fecha_entrega.strftime('%d/%m/%Y')} {format_horario(pedido.horario_entrega)}\n\n"
    
    # Productos
    mensaje += "🍫 Productos:\n\n"
    
    # Agrupar por tipo
    productos_por_tipo = {}
    for item in pedido.items:
        tipo = item.producto.tipo
        if tipo not in productos_por_tipo:
            productos_por_tipo[tipo] = []
        productos_por_tipo[tipo].append(item)
    
    for tipo, items in productos_por_tipo.items():
        tipo_nombre = "CHOCOLATE BLANCO" if tipo == "blanco" else "CHOCOLATE CON LECHE"
        mensaje += f"🍆 {tipo_nombre} {get_emoji_tipo(tipo)}\n"
        
        for item in items:
            mensaje += f"{item.cantidad} × {item.producto.tamano.title()} ({item.producto.peso}) {int(item.precio_unitario)} CUP\n"
        mensaje += "\n"
    
    # Totales
    mensaje += f"🛵 Mensajería: {int(pedido.precio_mensajeria)} CUP\n"
    mensaje += f"💰 Total: {int(pedido.total)} CUP\n\n"
    
    # Observaciones
    if pedido.observaciones:
        mensaje += f"🔍 Observaciones: {pedido.observaciones}\n\n"
    
    # Footer
    mensaje += "*Chocolates BYB*\n"
    mensaje += "Facebook: Chocolates B&b\n"
    mensaje += "Instagram: chocolates_byb\n"
    mensaje += "WhatsApp: +53 636 61888"
    
    return mensaje

def enviar_whatsapp(mensaje):
    try:
        if WHATSAPP_APIKEY == 'xxxxxx':
            print("WhatsApp not configured")
            print(mensaje)  # Print for debugging
            return True
        url = f"https://api.callmebot.com/whatsapp.php"
        params = {
            'phone': WHATSAPP_PHONE,
            'text': mensaje,
            'apikey': WHATSAPP_APIKEY
        }
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"WhatsApp Error: {e}")
        return False

# Aproximadamente línea 230-260: Modifica la función generar_informe_financiero
def generar_informe_financiero(inicio_fecha=None, fin_fecha=None):
    """Genera un informe financiero detallado para un período"""
    try:
        if not inicio_fecha:
            # Por defecto, el mes actual
            hoy = date.today()
            inicio_fecha = date(hoy.year, hoy.month, 1)
        
        if not fin_fecha:
            # Por defecto, fecha actual
            fin_fecha = date.today()
        
        # Consulta pedidos en el período
        pedidos = Pedido.query.filter(
            and_(
                func.date(Pedido.fecha_pedido) >= inicio_fecha,
                func.date(Pedido.fecha_pedido) <= fin_fecha,
                Pedido.estado.in_(['confirmado', 'entregado'])
            )
        ).all()
        
        # Calcular métricas
        total_ingresos = sum(p.total for p in pedidos) if pedidos else 0
        total_mensajeria = sum(p.precio_mensajeria for p in pedidos) if pedidos else 0
        
        # Costo de productos vendidos
        costo_productos = 0
        for pedido in pedidos:
            for item in pedido.items:
                if item.producto:
                    costo_productos += item.producto.costo * item.cantidad
        
        # Ganancia bruta y neta
        ganancia_bruta = total_ingresos - costo_productos
        ganancia_neta = ganancia_bruta - total_mensajeria  # Simplificado, se pueden añadir más gastos
        
        # Ventas por producto
        ventas_por_producto = defaultdict(lambda: {'cantidad': 0, 'ingresos': 0, 'costo': 0})
        for pedido in pedidos:
            for item in pedido.items:
                if item.producto:
                    ventas_por_producto[item.producto.nombre]['cantidad'] += item.cantidad
                    ventas_por_producto[item.producto.nombre]['ingresos'] += item.subtotal
                    ventas_por_producto[item.producto.nombre]['costo'] += item.producto.costo * item.cantidad
        
        # Ventas por día
        ventas_por_dia = defaultdict(float)
        for pedido in pedidos:
            dia = pedido.fecha_pedido.strftime('%Y-%m-%d')
            ventas_por_dia[dia] += pedido.total
        
        # Métricas por zona
        ventas_por_zona = defaultdict(float)
        for pedido in pedidos:
            zona = f"{pedido.cliente_municipio} - {pedido.cliente_reparto}"
            ventas_por_zona[zona] += pedido.total
        
        return {
            'periodo': {
                'inicio': inicio_fecha.strftime('%Y-%m-%d'),
                'fin': fin_fecha.strftime('%Y-%m-%d'),
            },
            'resumen': {
                'total_pedidos': len(pedidos),
                'total_ingresos': total_ingresos,
                'costo_productos': costo_productos,
                'total_mensajeria': total_mensajeria,
                'ganancia_bruta': ganancia_bruta,
                'ganancia_neta': ganancia_neta,
                'margen_ganancia': (ganancia_neta / total_ingresos * 100) if total_ingresos > 0 else 0
            },
            'ventas_por_producto': dict(ventas_por_producto),
            'ventas_por_dia': dict(ventas_por_dia),
            'ventas_por_zona': dict(ventas_por_zona)
        }
    except Exception as e:
        print(f"Error en generar_informe_financiero: {e}")
        # Devolver un informe vacío en caso de error
        return {
            'periodo': {
                'inicio': inicio_fecha.strftime('%Y-%m-%d') if inicio_fecha else '',
                'fin': fin_fecha.strftime('%Y-%m-%d') if fin_fecha else '',
            },
            'resumen': {
                'total_pedidos': 0,
                'total_ingresos': 0,
                'costo_productos': 0,
                'total_mensajeria': 0,
                'ganancia_bruta': 0,
                'ganancia_neta': 0,
                'margen_ganancia': 0
            },
            'ventas_por_producto': {},
            'ventas_por_dia': {},
            'ventas_por_zona': {}
        }

def generar_grafico_ventas(periodo='mes'):
    """Genera un gráfico de ventas para el dashboard"""
    hoy = date.today()
    
    if periodo == 'semana':
        inicio = hoy - timedelta(days=7)
        agrupacion = func.date(Pedido.fecha_pedido)
        formato = '%d/%m'
    elif periodo == 'mes':
        inicio = date(hoy.year, hoy.month, 1)
        agrupacion = func.date(Pedido.fecha_pedido)
        formato = '%d/%m'
    elif periodo == 'año':
        inicio = date(hoy.year, 1, 1)
        agrupacion = extract('month', Pedido.fecha_pedido)
        formato = '%m/%Y'
    else:
        inicio = date(hoy.year, 1, 1)
        agrupacion = extract('month', Pedido.fecha_pedido)
        formato = '%m/%Y'
    
    # Consulta SQL para obtener ventas agrupadas por período
    ventas = db.session.query(
        agrupacion.label('fecha'),
        func.sum(Pedido.total).label('total')
    ).filter(
        func.date(Pedido.fecha_pedido) >= inicio,
        Pedido.estado.in_(['confirmado', 'entregado'])
    ).group_by(agrupacion).all()
    
    # Preparar datos para el gráfico
    fechas = []
    totales = []
    
    for v in ventas:
        if periodo == 'año':
            # Si es por año, necesitamos convertir el número de mes a fecha
            fecha_obj = date(hoy.year, int(v.fecha), 1)
            fechas.append(fecha_obj.strftime(formato))
        else:
            fechas.append(v.fecha.strftime(formato) if hasattr(v.fecha, 'strftime') else str(v.fecha))
        totales.append(float(v.total))
    
    # Crear gráfico con matplotlib
    plt.figure(figsize=(10, 5))
    plt.bar(fechas, totales, color='#6B4423')
    plt.xlabel('Fecha')
    plt.ylabel('Ventas (CUP)')
    plt.title(f'Ventas por {periodo}')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Convertir gráfico a imagen base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    imagen = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    
    return f"data:image/png;base64,{imagen}"

def verificar_inventario():
    """Verifica el inventario y genera alertas"""
    productos_bajos = Producto.query.filter(
        and_(
            Producto.stock < 10,
            Producto.activo == True
        )
    ).all()
    
    materias_primas_bajas = MateriaPrima.query.filter(
        MateriaPrima.stock < MateriaPrima.nivel_alerta
    ).all()
    
    return {
        'productos_bajos': productos_bajos,
        'materias_primas_bajas': materias_primas_bajas
    }

def analizar_clientes():
    """Analiza clientes para identificar frecuentes y potenciales"""
    # Clientes frecuentes (más de 3 pedidos)
    clientes_frecuentes = Cliente.query.filter(
        Cliente.pedidos_completados >= 3
    ).order_by(Cliente.total_gastado.desc()).limit(10).all()
    
    # Clientes inactivos (sin pedidos en los últimos 2 meses)
    dos_meses_atras = datetime.now() - timedelta(days=60)
    clientes_inactivos = Cliente.query.filter(
        and_(
            Cliente.pedidos_completados > 0,
            Cliente.ultimo_pedido < dos_meses_atras
        )
    ).all()
    
    return {
        'clientes_frecuentes': clientes_frecuentes,
        'clientes_inactivos': clientes_inactivos
    }

def calcular_estadisticas():
    hoy = datetime.now().date()
    inicio_mes = datetime(hoy.year, hoy.month, 1).date()
    
    pedidos_hoy = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) == hoy
    ).count()
    
    pedidos_mes = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) >= inicio_mes
    ).count()
    
    # INGRESOS del mes (total que pagan los clientes)
    ingresos_mes = db.session.query(db.func.sum(Pedido.total)).filter(
        db.func.date(Pedido.fecha_pedido) >= inicio_mes,
        Pedido.estado.in_(['pendiente', 'confirmado', 'entregado'])
    ).scalar() or 0
    
    # GANANCIAS del mes (ingresos - costos)
    # Primero obtenemos todos los pedidos del mes
    pedidos_del_mes = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) >= inicio_mes,
        Pedido.estado.in_(['pendiente', 'confirmado', 'entregado'])
    ).all()
    
    ganancia_total = 0
    for pedido in pedidos_del_mes:
        for item in pedido.items:
            if item.producto:
                # Ganancia = (precio_venta - costo) * cantidad
                ganancia_item = (item.producto.precio - item.producto.costo) * item.cantidad
                ganancia_total += ganancia_item
    
    # Calcular margen de ganancia
    margen_ganancia = (ganancia_total / ingresos_mes * 100) if ingresos_mes > 0 else 0
    
    # Producto más vendido
    producto_top = db.session.query(
        Producto.nombre,
        db.func.sum(ItemPedido.cantidad).label('total')
    ).join(ItemPedido).group_by(Producto.id).order_by(db.desc('total')).first()
    
    # Alertas de inventario
    alertas_inventario = Producto.query.filter(
        Producto.stock < 10,
        Producto.activo == True
    ).count()
    
    # Alertas de margen de ganancia
    alertas_margen = Producto.query.filter(
        (Producto.precio - Producto.costo) / Producto.precio * 100 < 30,
        Producto.precio > 0,
        Producto.activo == True
    ).count()
    
    return {
        'pedidos_hoy': pedidos_hoy,
        'pedidos_mes': pedidos_mes,
        'ingresos_mes': ingresos_mes,
        'ganancia_mes': ganancia_total,
        'margen_ganancia': margen_ganancia,
        'producto_top': producto_top[0] if producto_top else 'N/A',
        'alertas_inventario': alertas_inventario,
        'alertas_margen': alertas_margen
    }

# ZONAS DE ENTREGA DATA
ZONAS_DATA = {
    'Guanabacoa': {
        'Semáforo Guanabacoa': 1350, 'Habana Nueva': 1350, 'Azotea': 1350, 
        'De Beche': 1450, 'Guanabacoa': 1450, 'Nalón': 1500, 'Chibás': 1450,
        'La Lima': 1550, 'Naranjo': 1500, 'La Hata': 1750, 'Gisela': 1450,
        'El Roble': 1500, 'Villa María': 1550, 'Alturas de Villa María': 1550,
        'Cruz Verde': 1400, 'Santa Fé': 2150, 'La Yuca': 1150, 'Los Mangos': 1750
    },
    'San Miguel': {
        'Luyanó Moderno': 1200, 'Afán': 1200, 'La Corea': 1250, 'Monterrey': 1100,
        'Mirta': 1350, 'El Diezmero': 1350, 'San Francisco de Paula': 1350,
        'San Juan de los Pinos': 1200, 'Vista Hermosa': 1250, 'Jacomino': 1100,
        'Barrio Obrero': 1100, 'Ciudamar': 1150, 'El Lucero': 1050, 'Juanelo': 1100,
        'California': 1150, 'Martin Pérez': 1200, 'Rocafort': 1150, 'La Cumbre': 1150,
        'Las Palmas': 1300, 'Dolores': 1100, 'Veracruz': 1150, 'María Luisa': 1200,
        'San Matías': 1150, 'Tejas': 1150, 'Prosperidad': 1400, 'Reboredo': 1450,
        'La Rosita': 1250, 'Villa Alegre': 1200, 'Siboney': 1450, 'Encanto': 1300,
        'San Pedro': 1350, 'Alturas de Luyanó': 1150, 'Virgen del Camino': 1050,
        'Bella Vista': 1400, 'Carolina': 1200
    },
    'Marianao': {
        'Todo Marianao': 500, 'CUJAE': 600
    },
    'Playa': {
        'Almendares': 500, 'Buena Vista': 500, 'Querejeta': 500, 'Jaimanitas': 500,
        'Flores': 500, 'Náutico': 500, 'Siboney': 500, 'Atabey': 500,
        'Miramar': 550, 'Kholy': 550, 'La Ceiba': 550, 'Santa Fé': 600
    },
    'La Lisa': {
        'La Lisa': 500, 'San Agustín': 500, 'Arroyo Arenas': 550, 'El Cano': 700,
        'XX Aniversario': 800, 'Valle Grande': 800, 'Punta Brava': 900, 'Guatao': 1000
    },
    'Plaza': {
        'Vedado': 750, 'Nuevo Vedado': 750
    },
    'Centro Habana': {
        'Todo Centro Habana': 900
    },
    'Habana Vieja': {
        'Todo Habana Vieja': 950
    },
    'Boyeros': {
        'Altahabana': 700, 'El Chico': 850, 'Wajay': 1050, 'Fontanar': 1100,
        'Abel Santamaría': 1100, 'Río Verde': 1050, '1ro de Mayo': 1100,
        'Baluarte': 1100, 'Mazorra': 1200, 'Calabazar': 1300, 'Panamerican': 1050,
        'Lutgardita': 1050, 'Santiago de Las Vegas': 1450, 'Mulgoba': 1350,
        'Boyeros': 1300, 'Nuevo Santiago': 1550
    },
    'Cerro': {
        'Martí': 750, 'Ciudad Deportiva': 750, 'Palatino': 800, 
        'Casino Deportivo': 800, 'Cerro': 950, 'El Canal': 900,
        'Villanueva': 950, 'Latinoamericano': 950, 'Atarés': 950
    },
    '10 de Octubre': {
        'Sevillano': 950, 'Mónaco': 950, 'La Víbora': 900, 'Santos Suárez': 900,
        'Acosta': 950, 'Luyanó': 1000, 'Lawton': 1000, 'Vista Alegre': 1100
    },
    'Arroyo Naranjo': {
        'Los Pinos': 850, 'Aldabó': 800, 'Poey': 900, 'Víbora Park': 1000,
        'Capri': 950, 'Vieja Linda': 900, 'Santa Amalia': 950, 'La Palma': 950,
        'Mantilla': 1000, 'Párraga': 1000, 'La Solita': 1000, 'Eléctrico': 1300,
        'Guinera': 1050
    }
}

# CREATE TABLES AND INITIAL DATA
with app.app_context():
    db.create_all()
    
    # Create admin user
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(
            username='admin',
            password=generate_password_hash('chocolates123')
        )
        db.session.add(admin)
        db.session.commit()
    
    # Clear old products and add new ones
    if Producto.query.count() == 0:
        # Delete old products if any
        Producto.query.delete()
        
        # New product structure
        productos_nuevos = [
            # Chocolate Blanco
            Producto(nombre="Chocolate Blanco Grande", tipo="blanco", tamano="grande", 
                    peso="230g", precio=1900, descripcion="Delicioso chocolate blanco artesanal"),
            Producto(nombre="Chocolate Blanco Mediano", tipo="blanco", tamano="mediano", 
                    peso="50g", precio=360, descripcion="Chocolate blanco perfecto para regalo"),
            Producto(nombre="Chocolate Blanco Pequeño", tipo="blanco", tamano="pequeno", 
                    peso="15g", precio=180, descripcion="Bocado de chocolate blanco"),
            Producto(nombre="Chocolate Blanco Vulva", tipo="blanco", tamano="vulva", 
                    peso="25g", precio=360, descripcion="Diseño especial y atrevido"),
            
            # Chocolate con Leche
            Producto(nombre="Chocolate con Leche Grande", tipo="con_leche", tamano="grande", 
                    peso="230g", precio=1900, descripcion="Cremoso chocolate con leche artesanal"),
            Producto(nombre="Chocolate con Leche Mediano", tipo="con_leche", tamano="mediano", 
                    peso="50g", precio=360, descripcion="Chocolate con leche ideal para compartir"),
            Producto(nombre="Chocolate con Leche Pequeño", tipo="con_leche", tamano="pequeno", 
                    peso="15g", precio=180, descripcion="Pequeña delicia de chocolate con leche"),
            Producto(nombre="Chocolate con Leche Vulva", tipo="con_leche", tamano="vulva", 
                    peso="25g", precio=360, descripcion="Diseño especial y atrevido")
        ]
        
        for producto in productos_nuevos:
            db.session.add(producto)
        
        db.session.commit()
    
    # Load zones if empty
    if ZonaEntrega.query.count() == 0:
        for municipio, repartos in ZONAS_DATA.items():
            for reparto, precio in repartos.items():
                zona = ZonaEntrega(
                    municipio=municipio,
                    reparto=reparto,
                    precio_mensajeria=precio
                )
                db.session.add(zona)
        db.session.commit()
        
    # Crear algunas materias primas iniciales si no existen
    if MateriaPrima.query.count() == 0:
        materias_primas_default = [
            MateriaPrima(nombre="Chocolate Blanco", unidad="kg", stock=5.0, costo_unitario=2500, nivel_alerta=1.0),
            MateriaPrima(nombre="Chocolate con Leche", unidad="kg", stock=5.0, costo_unitario=2200, nivel_alerta=1.0),
            MateriaPrima(nombre="Esencia de Vainilla", unidad="ml", stock=200, costo_unitario=5, nivel_alerta=50),
            MateriaPrima(nombre="Azúcar", unidad="kg", stock=10.0, costo_unitario=500, nivel_alerta=2.0),
            MateriaPrima(nombre="Leche en Polvo", unidad="kg", stock=3.0, costo_unitario=1800, nivel_alerta=0.5),
            MateriaPrima(nombre="Moldes", unidad="unidad", stock=50, costo_unitario=350, nivel_alerta=10)
        ]
        
        for mp in materias_primas_default:
            db.session.add(mp)
        
        db.session.commit()

# PUBLIC ROUTES
@app.route('/')
def index():
    productos_destacados = Producto.query.filter_by(activo=True).all()
    return render_template('index.html', productos=productos_destacados)

@app.route('/catalogo')
def catalogo():
    tipo = request.args.get('tipo', 'todos')
    if tipo == 'todos':
        productos = Producto.query.filter_by(activo=True).all()
    else:
        productos = Producto.query.filter_by(activo=True, tipo=tipo).all()
    return render_template('catalogo.html', productos=productos, tipo_actual=tipo)

@app.route('/api/zonas/<municipio>')
def get_zonas_municipio(municipio):
    zonas = ZonaEntrega.query.filter_by(municipio=municipio, disponible=True).all()
    return jsonify([{
        'reparto': z.reparto,
        'precio': z.precio_mensajeria
    } for z in zonas])

# Aproximadamente línea 340-400: Modifica la ruta /crear-pedido
@app.route('/crear-pedido', methods=['POST'])
def crear_pedido():
    try:
        data = request.json
        
        # Create order
        pedido = Pedido(
            numero_orden=get_next_order_number(),
            fecha_entrega=datetime.strptime(data['fecha_entrega'], '%Y-%m-%d').date(),
            horario_entrega=data['horario_entrega'],
            cliente_nombre=data['cliente_nombre'],
            cliente_telefono=data['cliente_telefono'],
            cliente_direccion_calle=data['cliente_direccion_calle'],
            cliente_municipio=data['cliente_municipio'],
            cliente_reparto=data['cliente_reparto'],
            observaciones=data.get('observaciones', ''),
            precio_mensajeria=float(data['precio_mensajeria']),
            subtotal=0,
            total=0
        )
        
        db.session.add(pedido)
        db.session.flush()  # Get the ID
        
        # Add items
        subtotal = 0
        for item_data in data['items']:
            producto = Producto.query.get(item_data['producto_id'])
            if not producto:
                continue
                
            cantidad = int(item_data['cantidad'])
            precio_unitario = producto.precio
            item_subtotal = precio_unitario * cantidad
            
            item = ItemPedido(
                pedido_id=pedido.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                subtotal=item_subtotal
            )
            db.session.add(item)
            subtotal += item_subtotal
            
            # Update stock
            producto.stock -= cantidad
        
        # Update totals
        pedido.subtotal = subtotal
        pedido.total = subtotal + pedido.precio_mensajeria
        
        # Actualizar cliente (nuevo método)
        cliente = Cliente.query.filter_by(telefono=pedido.cliente_telefono).first()
        
        if not cliente:
            cliente = Cliente(
                nombre=pedido.cliente_nombre,
                telefono=pedido.cliente_telefono,
                direccion_calle=pedido.cliente_direccion_calle,
                municipio=pedido.cliente_municipio,
                reparto=pedido.cliente_reparto,
                fecha_registro=datetime.utcnow(),
                ultimo_pedido=pedido.fecha_pedido,
                pedidos_completados=1,
                total_gastado=pedido.total
            )
        else:
            cliente.ultimo_pedido = pedido.fecha_pedido
            cliente.pedidos_completados += 1
            cliente.total_gastado += pedido.total
            # Actualizar dirección si ha cambiado
            if pedido.cliente_direccion_calle:
                cliente.direccion_calle = pedido.cliente_direccion_calle
            if pedido.cliente_municipio:
                cliente.municipio = pedido.cliente_municipio
            if pedido.cliente_reparto:
                cliente.reparto = pedido.cliente_reparto
        
        db.session.add(cliente)
        
        db.session.commit()
        
        # Send WhatsApp
        mensaje = format_whatsapp_message(pedido)
        enviar_whatsapp(mensaje)
        
        return jsonify({
            'success': True,
            'numero_orden': pedido.numero_orden,
            'mensaje': f'Pedido #{pedido.numero_orden} creado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error en crear_pedido: {e}")
        return jsonify({'error': str(e)}), 500
# ADMIN ROUTES
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and check_password_hash(usuario.password, password):
            session['user_id'] = usuario.id
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error='Credenciales invalidas')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    stats = calcular_estadisticas()
    pedidos_recientes = Pedido.query.order_by(Pedido.fecha_pedido.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, pedidos=pedidos_recientes)

@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    estado = request.args.get('estado', 'todos')
    if estado == 'todos':
        pedidos = Pedido.query.order_by(Pedido.fecha_pedido.desc()).all()
    else:
        pedidos = Pedido.query.filter_by(estado=estado).order_by(Pedido.fecha_pedido.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos, estado_actual=estado)

@app.route('/admin/pedido/<int:id>')
@login_required
def ver_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    return render_template('admin/pedido_detalle.html', pedido=pedido)

@app.route('/admin/pedido/<int:id>/estado', methods=['POST'])
@login_required
def cambiar_estado_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    pedido.estado = request.json['estado']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/productos')
@login_required
def admin_productos():
    productos = Producto.query.all()
    return render_template('admin/productos.html', productos=productos)

@app.route('/admin/producto/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_producto():
    if request.method == 'POST':
        try:
            imagen_filename = None
            
            # Handle image upload
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename and allowed_file(file.filename):
                    # Create safe filename
                    original_filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename_parts = original_filename.rsplit('.', 1)
                    imagen_filename = f"{filename_parts[0]}_{timestamp}.{filename_parts[1]}"
                    
                    # Save file
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
                    file.save(filepath)
            
            producto = Producto(
                nombre=request.form['nombre'],
                descripcion=request.form['descripcion'],
                tipo=request.form['tipo'],
                tamano=request.form['tamano'],
                peso=request.form['peso'],
                precio=float(request.form['precio']),
                costo=float(request.form.get('costo', 0)),  # AGREGAR ESTA LÍNEA
                stock=int(request.form['stock']),
                imagen=imagen_filename
            )
            
            db.session.add(producto)
            db.session.commit()
            
            return redirect(url_for('admin_productos'))
            
        except Exception as e:
            db.session.rollback()
            return render_template('admin/producto_form.html', error=str(e))
    
    return render_template('admin/producto_form.html')

@app.route('/admin/producto/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    producto = Producto.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            producto.nombre = request.form['nombre']
            producto.descripcion = request.form['descripcion']  
            producto.tipo = request.form['tipo']
            producto.tamano = request.form['tamano']
            producto.peso = request.form['peso']
            producto.precio = float(request.form['precio'])
            producto.costo = float(request.form.get('costo', 0))  # AGREGAR ESTA LÍNEA
            producto.stock = int(request.form['stock'])
            
            # Handle new image if uploaded
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename and allowed_file(file.filename):
                    # Delete old image if exists
                    if producto.imagen:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], producto.imagen)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    # Save new image
                    original_filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename_parts = original_filename.rsplit('.', 1)
                    imagen_filename = f"{filename_parts[0]}_{timestamp}.{filename_parts[1]}"
                    
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
                    file.save(filepath)
                    producto.imagen = imagen_filename
            
            db.session.commit()
            return redirect(url_for('admin_productos'))
            
        except Exception as e:
            db.session.rollback()
            return render_template('admin/producto_form.html', producto=producto, error=str(e))
    
    return render_template('admin/producto_form.html', producto=producto)

@app.route('/admin/producto/<int:id>/toggle')
@login_required
def toggle_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()
    return redirect(url_for('admin_productos'))

@app.route('/admin/producto/<int:id>/eliminar')
@login_required
def eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    
    try:
        # Delete image file if exists
        if producto.imagen:
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], producto.imagen)
            if os.path.exists(imagen_path):
                os.remove(imagen_path)
        
        # Delete product
        db.session.delete(producto)
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error eliminando producto: {e}")
    
    return redirect(url_for('admin_productos'))

@app.route('/admin/zonas')
@login_required
def admin_zonas():
    zonas = ZonaEntrega.query.order_by(ZonaEntrega.municipio, ZonaEntrega.reparto).all()
    return render_template('admin/zonas.html', zonas=zonas)

@app.route('/admin/zona/nueva', methods=['POST'])
@login_required
def nueva_zona():
    try:
        zona = ZonaEntrega(
            municipio=request.form['municipio'],
            reparto=request.form['reparto'],
            precio_mensajeria=float(request.form['precio']),
            disponible=True
        )
        db.session.add(zona)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error agregando zona: {e}")
    
    return redirect(url_for('admin_zonas'))

@app.route('/admin/zona/<int:id>/editar', methods=['POST'])
@login_required
def editar_zona(id):
    zona = ZonaEntrega.query.get_or_404(id)
    try:
        zona.precio_mensajeria = float(request.form['precio'])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error editando zona: {e}")
    
    return redirect(url_for('admin_zonas'))

@app.route('/admin/zona/<int:id>/toggle')
@login_required
def toggle_zona(id):
    zona = ZonaEntrega.query.get_or_404(id)
    zona.disponible = not zona.disponible
    db.session.commit()
    return redirect(url_for('admin_zonas'))

@app.route('/admin/exportar-pedidos')
@login_required
def exportar_pedidos():
    pedidos = Pedido.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow(['Orden', 'Fecha', 'Cliente', 'Telefono', 'Municipio', 
                     'Reparto', 'Productos', 'Mensajeria', 'Total', 'Estado'])
    
    for pedido in pedidos:
        productos_str = "; ".join([f"{item.cantidad}x {item.producto.nombre}" 
                                   for item in pedido.items])
        writer.writerow([
            f"#{pedido.numero_orden}",
            pedido.fecha_pedido.strftime('%Y-%m-%d'),
            pedido.cliente_nombre,
            pedido.cliente_telefono,
            pedido.cliente_municipio,
            pedido.cliente_reparto,
            productos_str,
            f"{pedido.precio_mensajeria:.2f}",
            f"{pedido.total:.2f}",
            pedido.estado
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'pedidos_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/admin/reiniciar-pedidos')
@login_required
def reiniciar_pedidos():
    try:
        # Eliminar todos los items de pedidos primero
        ItemPedido.query.delete()
        # Luego eliminar todos los pedidos
        Pedido.query.delete()
        db.session.commit()
        
        # Mensaje de éxito (opcional, puedes usar flash messages)
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        db.session.rollback()
        print(f"Error reiniciando pedidos: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/financiero')
@login_required
def admin_financiero():
    # Por defecto muestra datos del mes actual
    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    
    informe = generar_informe_financiero(inicio_mes, hoy)
    grafico_ventas = generar_grafico_ventas('mes')
    
    # Productos más rentables
    productos_rentables = []
    for nombre, datos in informe['ventas_por_producto'].items():
        if datos['ingresos'] > 0:
            ganancia = datos['ingresos'] - datos['costo']
            margen = (ganancia / datos['ingresos']) * 100
            productos_rentables.append({
                'nombre': nombre,
                'cantidad': datos['cantidad'],
                'ingresos': datos['ingresos'],
                'ganancia': ganancia,
                'margen': margen
            })
    
    productos_rentables.sort(key=lambda x: x['ganancia'], reverse=True)
    
    return render_template(
        'admin/financiero.html',
        informe=informe,
        grafico_ventas=grafico_ventas,
        productos_rentables=productos_rentables[:5]  # Top 5
    )

@app.route('/admin/financiero/reporte', methods=['GET', 'POST'])
@login_required
def reporte_financiero():
    if request.method == 'POST':
        inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d').date()
        fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d').date()
        tipo_reporte = request.form.get('tipo_reporte', 'completo')
        
        informe = generar_informe_financiero(inicio, fin)
        
        # Si solicitan exportación
        if 'exportar' in request.form:
            formato = request.form.get('formato', 'csv')
            
            if formato == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Cabecera
                writer.writerow(['Informe Financiero', f'Periodo: {inicio} al {fin}'])
                writer.writerow([])
                
                # Resumen
                writer.writerow(['Resumen'])
                for key, value in informe['resumen'].items():
                    writer.writerow([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else value])
                
                writer.writerow([])
                
                # Ventas por producto
                writer.writerow(['Producto', 'Cantidad', 'Ingresos', 'Costo', 'Ganancia', 'Margen (%)'])
                for nombre, datos in informe['ventas_por_producto'].items():
                    ganancia = datos['ingresos'] - datos['costo']
                    margen = (ganancia / datos['ingresos'] * 100) if datos['ingresos'] > 0 else 0
                    writer.writerow([
                        nombre, 
                        datos['cantidad'],
                        f"{datos['ingresos']:.2f}",
                        f"{datos['costo']:.2f}",
                        f"{ganancia:.2f}",
                        f"{margen:.2f}%"
                    ])
                
                output.seek(0)
                return send_file(
                    io.BytesIO(output.getvalue().encode('utf-8')),
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'informe_financiero_{inicio}_{fin}.csv'
                )
            
            # Podría añadirse soporte para PDF u otros formatos aquí
        
        return render_template(
            'admin/reporte_financiero.html',
            informe=informe,
            inicio=inicio,
            fin=fin,
            tipo_reporte=tipo_reporte
        )
    
    # Si es GET, mostrar formulario
    return render_template('admin/reporte_financiero_form.html')

# Aproximadamente línea 700-730: Corrige la ruta /admin/clientes
@app.route('/admin/clientes')
@login_required
def admin_clientes():
    try:
        # Obtener todos los clientes para la pestaña "todos"
        clientes_todos = Cliente.query.all()
        
        # Clientes frecuentes (más de 3 pedidos)
        clientes_frecuentes = Cliente.query.filter(
            Cliente.pedidos_completados >= 3
        ).order_by(Cliente.total_gastado.desc()).limit(10).all()
        
        # Clientes inactivos (sin pedidos en los últimos 2 meses)
        dos_meses_atras = datetime.now() - timedelta(days=60)
        clientes_inactivos = Cliente.query.filter(
            and_(
                Cliente.pedidos_completados > 0,
                Cliente.ultimo_pedido < dos_meses_atras
            )
        ).all()
        
        # Para la plantilla, necesitamos la fecha actual para calcular días inactivos
        now = datetime.now()
        
        return render_template(
            'admin/clientes.html',
            clientes_frecuentes=clientes_frecuentes,
            clientes_inactivos=clientes_inactivos,
            clientes_todos=clientes_todos,
            now=now
        )
    except Exception as e:
        print(f"Error en admin_clientes: {e}")
        # En caso de error, devolver listas vacías
        return render_template(
            'admin/clientes.html',
            clientes_frecuentes=[],
            clientes_inactivos=[],
            clientes_todos=[],
            now=datetime.now(),
            error=str(e)
        )
@app.route('/admin/inventario')
@login_required
def admin_inventario():
    productos = Producto.query.all()
    materias_primas = MateriaPrima.query.all()
    alertas = verificar_inventario()
    
    return render_template(
        'admin/inventario.html',
        productos=productos,
        materias_primas=materias_primas,
        alertas=alertas
    )

@app.route('/admin/producto/ajustar-stock', methods=['POST'])
@login_required
def ajustar_stock_producto():
    try:
        producto_id = request.form.get('producto_id')
        nuevo_stock = request.form.get('nuevo_stock')
        motivo = request.form.get('motivo_ajuste')
        notas = request.form.get('notas_ajuste')
        
        producto = Producto.query.get_or_404(producto_id)
        producto.stock = int(nuevo_stock)
        
        db.session.commit()
        
        return redirect(url_for('admin_inventario'))
    except Exception as e:
        db.session.rollback()
        print(f"Error ajustando stock: {e}")
        return redirect(url_for('admin_inventario'))

@app.route('/admin/materia-prima/editar', methods=['POST'])
@login_required
def editar_materia_prima():
    try:
        materia_prima_id = request.form.get('materia_prima_id')
        nombre = request.form.get('nombre')
        unidad = request.form.get('unidad')
        stock = request.form.get('stock')
        costo_unitario = request.form.get('costo_unitario')
        proveedor = request.form.get('proveedor')
        nivel_alerta = request.form.get('nivel_alerta')
        notas = request.form.get('notas')
        
        materia_prima = MateriaPrima.query.get_or_404(materia_prima_id)
        materia_prima.nombre = nombre
        materia_prima.unidad = unidad
        materia_prima.stock = float(stock)
        materia_prima.costo_unitario = float(costo_unitario)
        materia_prima.proveedor = proveedor
        materia_prima.nivel_alerta = float(nivel_alerta)
        materia_prima.notas = notas
        
        db.session.commit()
        
        return redirect(url_for('admin_inventario'))
    except Exception as e:
        db.session.rollback()
        print(f"Error editando materia prima: {e}")
        return redirect(url_for('admin_inventario'))

@app.route('/admin/recetas')
@login_required
def admin_recetas():
    recetas = Receta.query.all()
    productos = Producto.query.all()
    materias_primas = MateriaPrima.query.all()
    
    # Si se especifica un producto, filtrar solo esa receta
    producto_id = request.args.get('producto')
    if producto_id:
        recetas = Receta.query.filter_by(producto_id=producto_id).all()
    
    return render_template(
        'admin/recetas.html',
        recetas=recetas,
        productos=productos,
        materias_primas=materias_primas
    )

@app.route('/admin/receta/nueva', methods=['GET', 'POST'])
@login_required
def nueva_receta():
    if request.method == 'POST':
        producto_id = request.form['producto_id']
        ingredientes = json.loads(request.form['ingredientes'])
        
        receta = Receta(
            producto_id=producto_id,
            rendimiento=request.form.get('rendimiento', 1),
            tiempo_preparacion=request.form.get('tiempo_preparacion', 0),
            instrucciones=request.form.get('instrucciones', '')
        )
        
        db.session.add(receta)
        db.session.flush()  # Obtener ID
        
        costo_total = 0
        for ing in ingredientes:
            materia_prima = MateriaPrima.query.get(ing['id'])
            cantidad = float(ing['cantidad'])
            
            ingrediente = RecetaIngrediente(
                receta_id=receta.id,
                materia_prima_id=materia_prima.id,
                cantidad=cantidad
            )
            
            costo_total += materia_prima.costo_unitario * cantidad
            db.session.add(ingrediente)
        
        # Actualizar costo total y costo del producto
        receta.costo_total = costo_total
        
        producto = Producto.query.get(producto_id)
        costo_por_unidad = costo_total / receta.rendimiento
        producto.costo = costo_por_unidad
        
        db.session.commit()
        
        return redirect(url_for('admin_recetas'))
    
    productos = Producto.query.all()
    materias_primas = MateriaPrima.query.all()
    
    return render_template(
        'admin/receta_form.html',
        productos=productos,
        materias_primas=materias_primas
    )

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
