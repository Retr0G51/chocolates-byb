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
    tipo = db.Column(db.String(50))
    precio = db.Column(db.Float, nullable=False)
    costo = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=100)
    imagen = db.Column(db.String(200))
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    producto = db.relationship('Producto', backref='pedidos')
    cantidad = db.Column(db.Integer, default=1)
    fecha_entrega = db.Column(db.Date)
    horario_entrega = db.Column(db.String(20))
    cliente_nombre = db.Column(db.String(100))
    cliente_telefono = db.Column(db.String(20))
    cliente_direccion = db.Column(db.Text)
    nota = db.Column(db.Text)
    estado = db.Column(db.String(20), default='pendiente')
    total = db.Column(db.Float)
    ganancia = db.Column(db.Float)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# HELPER FUNCTIONS
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def enviar_whatsapp(mensaje):
    try:
        if WHATSAPP_APIKEY == 'xxxxxx':
            print("WhatsApp not configured")
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
        db.func.date(Pedido.creado_en) == hoy
    ).count()
    
    pedidos_mes = Pedido.query.filter(
        db.func.date(Pedido.creado_en) >= inicio_mes
    ).count()
    
    ganancias_mes = db.session.query(db.func.sum(Pedido.ganancia)).filter(
        db.func.date(Pedido.creado_en) >= inicio_mes,
        Pedido.estado == 'entregado'
    ).scalar() or 0
    
    producto_top = db.session.query(
        Producto.nombre,
        db.func.sum(Pedido.cantidad).label('total')
    ).join(Pedido).group_by(Producto.id).order_by(db.desc('total')).first()
    
    return {
        'pedidos_hoy': pedidos_hoy,
        'pedidos_mes': pedidos_mes,
        'ganancias_mes': ganancias_mes,
        'producto_top': producto_top[0] if producto_top else 'N/A'
    }

# CREATE TABLES AND INITIAL DATA
with app.app_context():
    db.create_all()
    
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(
            username='admin',
            password=generate_password_hash('chocolates123')
        )
        db.session.add(admin)
        db.session.commit()
    
    if Producto.query.count() == 0:
        productos = [
            Producto(
                nombre="Bombon Clasico",
                descripcion="Delicioso bombon de chocolate oscuro 70% cacao",
                tipo="oscuro",
                precio=2.50,
                costo=1.50,
                stock=50
            ),
            Producto(
                nombre="Trufa de Chocolate Blanco",
                descripcion="Suave trufa de chocolate blanco con centro cremoso",
                tipo="blanco",
                precio=3.00,
                costo=1.80,
                stock=30
            ),
            Producto(
                nombre="Chocolate con Leche y Almendras",
                descripcion="Tableta de chocolate con leche y almendras tostadas",
                tipo="con_leche",
                precio=5.00,
                costo=3.00,
                stock=25
            )
        ]
        for p in productos:
            db.session.add(p)
        db.session.commit()

# PUBLIC ROUTES
@app.route('/')
def index():
    productos_destacados = Producto.query.filter_by(activo=True).limit(6).all()
    return render_template('index.html', productos=productos_destacados)

@app.route('/catalogo')
def catalogo():
    tipo = request.args.get('tipo', 'todos')
    if tipo == 'todos':
        productos = Producto.query.filter_by(activo=True).all()
    else:
        productos = Producto.query.filter_by(activo=True, tipo=tipo).all()
    return render_template('catalogo.html', productos=productos, tipo_actual=tipo)

@app.route('/producto/<int:id>')
def ver_producto(id):
    producto = Producto.query.get_or_404(id)
    return render_template('producto.html', producto=producto)

@app.route('/crear-pedido', methods=['POST'])
def crear_pedido():
    try:
        data = request.json
        producto = Producto.query.get(data['producto_id'])
        
        if not producto or producto.stock < data['cantidad']:
            return jsonify({'error': 'Producto no disponible'}), 400
        
        total = producto.precio * data['cantidad']
        ganancia = (producto.precio - producto.costo) * data['cantidad']
        
        pedido = Pedido(
            producto_id=data['producto_id'],
            cantidad=data['cantidad'],
            fecha_entrega=datetime.strptime(data['fecha_entrega'], '%Y-%m-%d').date(),
            horario_entrega=data['horario_entrega'],
            cliente_nombre=data['cliente_nombre'],
            cliente_telefono=data['cliente_telefono'],
            cliente_direccion=data['cliente_direccion'],
            nota=data.get('nota', ''),
            total=total,
            ganancia=ganancia
        )
        
        producto.stock -= data['cantidad']
        
        db.session.add(pedido)
        db.session.commit()
        
        mensaje = f"""NUEVO PEDIDO - Chocolates ByB
Producto: {producto.nombre}
Cantidad: {data['cantidad']}
Fecha: {data['fecha_entrega']}
Cliente: {data['cliente_nombre']}
Direccion: {data['cliente_direccion']}
Total: ${total:.2f}"""
        
        enviar_whatsapp(mensaje)
        
        return jsonify({
            'success': True,
            'pedido_id': pedido.id,
            'mensaje': 'Pedido creado exitosamente'
        })
        
    except Exception as e:
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
    pedidos_recientes = Pedido.query.order_by(Pedido.creado_en.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, pedidos=pedidos_recientes)

@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    estado = request.args.get('estado', 'todos')
    if estado == 'todos':
        pedidos = Pedido.query.order_by(Pedido.creado_en.desc()).all()
    else:
        pedidos = Pedido.query.filter_by(estado=estado).order_by(Pedido.creado_en.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos, estado_actual=estado)

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
        imagen = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename:
                filename = secure_filename(file.filename)
                filename = f"{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen = filename
        
        producto = Producto(
            nombre=request.form['nombre'],
            descripcion=request.form['descripcion'],
            tipo=request.form['tipo'],
            precio=float(request.form['precio']),
            costo=float(request.form['costo']),
            stock=int(request.form['stock']),
            imagen=imagen
        )
        db.session.add(producto)
        db.session.commit()
        return redirect(url_for('admin_productos'))
    
    return render_template('admin/producto_form.html', producto=None)

@app.route('/admin/producto/<int:id>/toggle')
@login_required
def toggle_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()
    return redirect(url_for('admin_productos'))

@app.route('/admin/exportar-pedidos')
@login_required
def exportar_pedidos():
    pedidos = Pedido.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Fecha', 'Cliente', 'Producto', 'Cantidad', 'Total', 'Estado'])
    
    for pedido in pedidos:
        writer.writerow([
            pedido.id,
            pedido.creado_en.strftime('%Y-%m-%d'),
            pedido.cliente_nombre,
            pedido.producto.nombre if pedido.producto else 'N/A',
            pedido.cantidad,
            f"${pedido.total:.2f}",
            pedido.estado
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'pedidos_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
