from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

# Crear la instancia de SQLAlchemy que será importada por app.py
db = SQLAlchemy()

# Definir la zona horaria de Cuba
cuba_tz = pytz.timezone('America/Havana')

def obtener_hora_cuba():
    """Función auxiliar para obtener la hora actual en Cuba"""
    return datetime.now(cuba_tz)

class Usuario(db.Model):
    """
    Modelo para usuarios administrativos del sistema.
    Solo los administradores pueden acceder al panel de control.
    """
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(120))
    email = db.Column(db.String(120))
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_cuba)
    ultimo_acceso = db.Column(db.DateTime)
    
    def set_password(self, password):
        """Hashea y guarda la contraseña de forma segura"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica si la contraseña proporcionada es correcta"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Usuario {self.username}>'


class Producto(db.Model):
    """
    Modelo para los productos de chocolate.
    Cada producto tiene un tipo, tamaño y precio.
    """
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo_chocolate = db.Column(db.String(20), nullable=False)  # oscuro, leche, blanco
    tamano = db.Column(db.String(20), nullable=False)  # pequeno, grande
    peso_gramos = db.Column(db.Integer, nullable=False)  # 115g o 230g
    precio = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.Text)
    disponible = db.Column(db.Boolean, default=True)
    imagen_url = db.Column(db.String(255))  # URL de la imagen del producto
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_cuba)
    
    # Relación con pedidos (un producto puede estar en muchos pedidos)
    pedidos = db.relationship('ItemPedido', back_populates='producto')
    
    def __repr__(self):
        return f'<Producto {self.nombre} - {self.tamano}>'


class Cliente(db.Model):
    """
    Modelo para almacenar información de clientes.
    Cada cliente puede tener múltiples pedidos.
    """
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.Text)
    municipio = db.Column(db.String(50))
    zona = db.Column(db.String(100))
    email = db.Column(db.String(120))
    fecha_registro = db.Column(db.DateTime, default=obtener_hora_cuba)
    
    # Relación con pedidos (un cliente puede tener muchos pedidos)
    pedidos = db.relationship('Pedido', back_populates='cliente')
    
    def __repr__(self):
        return f'<Cliente {self.nombre} - {self.telefono}>'


class Pedido(db.Model):
    """
    Modelo principal para los pedidos.
    Contiene toda la información de un pedido específico.
    """
    __tablename__ = 'pedidos'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.Integer, unique=True, nullable=False)  # 1281, 1282, etc.
    
    # Información del cliente
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    cliente = db.relationship('Cliente', back_populates='pedidos')
    
    # Fechas importantes
    fecha_pedido = db.Column(db.DateTime, default=obtener_hora_cuba, nullable=False)
    fecha_entrega = db.Column(db.Date, nullable=False)
    horario_entrega = db.Column(db.String(20), nullable=False)  # "8:00-12:00", etc.
    
    # Información de entrega
    direccion_entrega = db.Column(db.Text, nullable=False)
    municipio_entrega = db.Column(db.String(50), nullable=False)
    zona_entrega = db.Column(db.String(100))
    costo_mensajeria = db.Column(db.Float, default=0)
    
    # Extras
    incluye_bolsa_regalo = db.Column(db.Boolean, default=False)
    incluye_tarjeta = db.Column(db.Boolean, default=False)
    nota_personalizada = db.Column(db.Text)
    
    # Totales
    subtotal = db.Column(db.Float, default=0)  # Total de productos
    total_extras = db.Column(db.Float, default=0)  # Total de extras
    total = db.Column(db.Float, default=0)  # Total final incluyendo mensajería
    
    # Estado del pedido
    estado = db.Column(db.String(20), default='PENDIENTE')  # PENDIENTE, COMPLETADO, CANCELADO
    modificado = db.Column(db.Boolean, default=False)
    fecha_modificacion = db.Column(db.DateTime)
    razon_modificacion = db.Column(db.Text)
    
    # Trabajadores asignados
    gestor_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    mensajero_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    elaborador_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    
    # Observaciones adicionales
    observaciones = db.Column(db.Text)
    
    # Relación con los items del pedido
    items = db.relationship('ItemPedido', back_populates='pedido', cascade='all, delete-orphan')
    
    def calcular_totales(self):
        """Calcula y actualiza los totales del pedido"""
        # Calcular subtotal de productos
        self.subtotal = sum(item.precio_total for item in self.items)
        
        # Calcular extras
        self.total_extras = 0
        if self.incluye_bolsa_regalo:
            self.total_extras += 200  # Precio de bolsa de regalo
        if self.incluye_tarjeta:
            self.total_extras += 150  # Precio de tarjeta
        
        # Total final
        self.total = self.subtotal + self.total_extras + self.costo_mensajeria
    
    def generar_mensaje_whatsapp(self):
        """Genera el mensaje formateado para WhatsApp"""
        # Construir el detalle de zonas de mensajería
        zonas_mensajeria = """🛵 Mensajería:

*-Habana del Este:* NO
*-Alamar:* NO
*-Cotorro:* NO
*-Regla:* NO
*-Guanabacoa:* (Semáforo Guanabacoa 1350, Habana Nueva 1350, Azotea 1350, De Beche 1450, Guanabacoa 1450, Nalón 1500, Chibás 1450, La Lima 1550, Naranjo 1500, La Hata 1750, Gisela 1450, El Roble 1500, Villa María 1550, Alturas de Villa María 1550, Cruz Verde 1400, Santa Fé 2150, La Yuca 1150, Los Mangos 1750, Barreras NO, La Gallega NO, Minas NO, Bacuranao NO, Peñalver NO, Arango NO, El Alecrín NO)
*-San Miguel:* (Luyanó Moderno 1200, Afán 1200, La Corea 1250, Monterrey 1100, Mirta 1350, El Diezmero 1350, San Francisco de Paula 1350, San Juan de los Pinos (La Cuevita) 1200, Vista Hermosa 1250, Jacomino 1100, Barrio Obrero 1100, Ciudamar 1150, El Lucero 1050, Juanelo 1100, California 1150, Martin Pérez 1200, Rocafort 1150, La Cumbre 1150, Las Palmas 1300, Dolores 1100, Veracruz 1150, María Luisa 1200, San Matías 1150, Tejas 1150, Prosperidad 1400, Reboredo 1450, La Rosita 1250, Villa Alegre 1200, Siboney 1450, Encanto 1300, San Pedro 1350, Alturas de Luyanó 1150, Las Palmas 1250, Virgen del Camino 1050, Bella Vista 1400, Carolina 1200)
*-Marianao:* (Todo 500, CUJAE 600 CUP)
*-Playa:* (Almendares 500, Buena Vista 500, Querejeta 500, Jaimanitas 500, Flores 500, Náutico 500, Siboney 500, Atabey 500, Miramar 550, Kholy: 550, La Ceiba 550, Santa Fé: 600)
*-La Lisa:* (La Lisa 500, San Agustín 500, Arroyo Arenas 550, El Cano 700, XX Aniversario 800, Valle Grande, 800, Punta Brava 900, Guatao 1000)
*-Plaza:* (Vedado 750, Nuevo Vedado 750)
*-Centro Habana:* (900)
*-Habana Vieja:* (950)
*-Boyeros:* (Altahabana 700, El Chico 850, Wajay 1050, Fontanar 1100, Abel Santamaría 1100, Río Verde 1050, 1ro de Mayo 1100, Baluarte 1100 CUP, Mazorra 1200, Calabazar 1300, Panamerican 1050 CUP, Lutgardita 1050, Santiago de Las Vegas 1450, Mulgoba 1350, Boyeros 1300, Nuevo Santiago 1550)
*-Cerro:* (Martí 750, Ciudad Deportiva 750, Palatino 800, Casino Deportivo 800, Cerro 950, El Canal 900, Villanueva 950, Latinoamericano 950, Atarés 950)
*-10 de Octubre:* (Sevillano 950, Mónaco 950, La Víbora 900, Santos Suárez 900, Acosta 950, Luyanó 1000, Lawton 1000, Vista Alegre 1100)
*-Arroyo Naranjo:* (Los Pinos 850, Aldabó 800, Poey 900, Víbora Park 1000, Capri 950, Vieja Linda 900, Santa Amalia 950, La Palma 950, Mantilla 1000, Párraga 1000, La Solita 1000, Eléctrico 1300, Guinera 1050)"""
        
        # Construir productos
        productos_texto = ""
        for item in self.items:
            emoji = "🍫" if item.producto.tipo_chocolate == "oscuro" else "🟤" if item.producto.tipo_chocolate == "leche" else "⚪"
            productos_texto += f"\n{emoji} {item.producto.nombre.upper()} {emoji}\n"
            productos_texto += f"{item.cantidad} × {item.producto.tamano.title()} ({item.producto.peso_gramos} g) {item.precio_total:.0f} CUP\n"
        
        # Construir extras
        extras_texto = ""
        if self.incluye_bolsa_regalo:
            extras_texto += "\n✨Bolsa de regalo: 200 CUP"
        if self.incluye_tarjeta:
            extras_texto += "\n💌Tarjeta personalizada: 150 CUP"
        
        # Construir mensaje completo
        mensaje = f"""🔸 *{self.numero_pedido} Orden de Factura* 🏷️

🗓️Fecha de pedido: {self.fecha_pedido.strftime('%d/%m/%Y')}
👤 Cliente: {self.cliente.nombre}
📞 Teléfono: {self.cliente.telefono}
📍 Dirección: {self.direccion_entrega}
🕒 Fecha y hora de entrega: {self.fecha_entrega.strftime('%d/%m/%Y')} {self.horario_entrega}

🍫 Producto: {productos_texto}{extras_texto}

🛵 Mensajería: {self.costo_mensajeria:.0f} CUP

{zonas_mensajeria}

(Si la entrega es en una de las zonas donde no llegamos, podemos encontrarnos en un punto cercano)
💰Total: {self.total:.0f} CUP

🔍Observaciones: {self.observaciones or 'Sin observaciones'}

*Chocolates BYB*
Facebook: Chocolates B&b
Instagram: chocolates_byb
Whatsapp: +53 636 61888"""
        
        return mensaje
    
    def __repr__(self):
        return f'<Pedido #{self.numero_pedido} - {self.cliente.nombre}>'


class ItemPedido(db.Model):
    """
    Modelo para los items individuales dentro de un pedido.
    Representa cada producto específico que forma parte del pedido.
    """
    __tablename__ = 'items_pedido'
    
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False)  # Precio al momento del pedido
    precio_total = db.Column(db.Float, nullable=False)  # cantidad * precio_unitario
    
    # Relaciones
    pedido = db.relationship('Pedido', back_populates='items')
    producto = db.relationship('Producto', back_populates='pedidos')
    
    def calcular_precio_total(self):
        """Calcula el precio total del item"""
        self.precio_total = self.cantidad * self.precio_unitario
    
    def __repr__(self):
        return f'<ItemPedido {self.cantidad}x {self.producto.nombre}>'


class Trabajador(db.Model):
    """
    Modelo para gestionar los trabajadores del negocio.
    Incluye mensajeros, gestores, elaboradores e inversionistas.
    """
    __tablename__ = 'trabajadores'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # MENSAJERO, GESTOR, ELABORADOR, INVERSIONISTA
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=obtener_hora_cuba)
    
    # Totales históricos
    total_ganado = db.Column(db.Float, default=0)
    pedidos_completados = db.Column(db.Integer, default=0)
    
    # Relación con transacciones
    transacciones = db.relationship('Transaccion', back_populates='trabajador')
    
    def __repr__(self):
        return f'<Trabajador {self.nombre} - {self.tipo}>'


class Transaccion(db.Model):
    """
    Modelo para registrar todas las transacciones financieras.
    Incluye ganancias, comisiones y gastos.
    """
    __tablename__ = 'transacciones'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo_transaccion = db.Column(db.String(30), nullable=False)  # VENTA, COMISION, GASTO, GANANCIA_NEGOCIO
    concepto = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=obtener_hora_cuba, nullable=False)
    
    # Referencias opcionales
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'))
    trabajador_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    
    # Relaciones
    pedido = db.relationship('Pedido')
    trabajador = db.relationship('Trabajador', back_populates='transacciones')
    
    # Campos adicionales
    observaciones = db.Column(db.Text)
    registrado_por = db.Column(db.String(50))  # Username del admin que registró
    
    def __repr__(self):
        return f'<Transaccion {self.tipo_transaccion} - {self.monto} CUP>'


class ConfiguracionTienda(db.Model):
    """
    Modelo para configuraciones generales de la tienda.
    Permite modificar ciertos parámetros sin tocar el código.
    """
    __tablename__ = 'configuracion_tienda'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)
    tipo_dato = db.Column(db.String(20))  # STRING, INTEGER, FLOAT, BOOLEAN
    descripcion = db.Column(db.String(200))
    fecha_actualizacion = db.Column(db.DateTime, default=obtener_hora_cuba, onupdate=obtener_hora_cuba)
    
    @staticmethod
    def obtener_valor(clave, valor_por_defecto=None):
        """Obtiene un valor de configuración de la base de datos"""
        config = ConfiguracionTienda.query.filter_by(clave=clave).first()
        if config:
            if config.tipo_dato == 'INTEGER':
                return int(config.valor)
            elif config.tipo_dato == 'FLOAT':
                return float(config.valor)
            elif config.tipo_dato == 'BOOLEAN':
                return config.valor.lower() == 'true'
            else:
                return config.valor
        return valor_por_defecto
    
    def __repr__(self):
        return f'<ConfiguracionTienda {self.clave}={self.valor}>'
