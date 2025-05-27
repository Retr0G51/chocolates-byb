import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import requests
import csv
import io
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

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
    return 1423  # Starting number

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

def calcular_estadisticas():
    hoy = datetime.now().date()
    inicio_mes = datetime(hoy.year, hoy.month, 1).date()
    
    pedidos_hoy = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) == hoy
    ).count()
    
    pedidos_mes = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) >= inicio_mes
    ).count()
    
    # CAMBIAR ESTO: usar total en lugar de ganancia
    ingresos_mes = db.session.query(db.func.sum(Pedido.total)).filter(
        db.func.date(Pedido.fecha_pedido) >= inicio_mes,
        Pedido.estado.in_(['pendiente', 'confirmado', 'entregado'])
    ).scalar() or 0
    
    # Producto más vendido
    producto_top = db.session.query(
        Producto.nombre,
        db.func.sum(ItemPedido.cantidad).label('total')
    ).join(ItemPedido).group_by(Producto.id).order_by(db.desc('total')).first()
    
    return {
        'pedidos_hoy': pedidos_hoy,
        'pedidos_mes': pedidos_mes,
        'ingresos_mes': ingresos_mes,
        'producto_top': producto_top[0] if producto_top else 'N/A'
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

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
