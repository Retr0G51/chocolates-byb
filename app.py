from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, date
from functools import wraps
import os
import requests
import pytz
from urllib.parse import quote

# Importar los modelos y configuración
from models import db, Usuario, Producto, Cliente, Pedido, ItemPedido, Trabajador, Transaccion, ConfiguracionTienda
from config import Config

# Crear la aplicación Flask
app = Flask(__name__)
app.config.from_object(Config)

# Inicializar la base de datos con la aplicación
db.init_app(app)

# Configurar la zona horaria de Cuba
cuba_tz = pytz.timezone('America/Havana')

# Crear todas las tablas si no existen
with app.app_context():
    db.create_all()
    
    # Crear usuario admin por defecto si no existe
    admin = Usuario.query.filter_by(username='admin').first()
    if not admin:
        admin = Usuario(username='admin', nombre_completo='Administrador Principal')
        admin.set_password('admin123')  # Cambiar en producción
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado con contraseña: admin123")
    
    # Crear productos de ejemplo si no existen
    if Producto.query.count() == 0:
        productos_iniciales = [
            # Chocolates oscuros
            Producto(
                nombre='Chocolate Oscuro',
                tipo_chocolate='oscuro',
                tamano='pequeno',
                peso_gramos=115,
                precio=950,
                descripcion='Delicioso chocolate oscuro artesanal 70% cacao',
                disponible=True
            ),
            Producto(
                nombre='Chocolate Oscuro',
                tipo_chocolate='oscuro',
                tamano='grande',
                peso_gramos=230,
                precio=1900,
                descripcion='Delicioso chocolate oscuro artesanal 70% cacao',
                disponible=True
            ),
            # Chocolates con leche
            Producto(
                nombre='Chocolate con Leche',
                tipo_chocolate='leche',
                tamano='pequeno',
                peso_gramos=115,
                precio=950,
                descripcion='Suave chocolate con leche artesanal',
                disponible=True
            ),
            Producto(
                nombre='Chocolate con Leche',
                tipo_chocolate='leche',
                tamano='grande',
                peso_gramos=230,
                precio=1900,
                descripcion='Suave chocolate con leche artesanal',
                disponible=True
            ),
            # Chocolates blancos
            Producto(
                nombre='Chocolate Blanco',
                tipo_chocolate='blanco',
                tamano='pequeno',
                peso_gramos=115,
                precio=950,
                descripcion='Cremoso chocolate blanco artesanal',
                disponible=True
            ),
            Producto(
                nombre='Chocolate Blanco',
                tipo_chocolate='blanco',
                tamano='grande',
                peso_gramos=230,
                precio=1900,
                descripcion='Cremoso chocolate blanco artesanal',
                disponible=True
            )
        ]
        
        for producto in productos_iniciales:
            db.session.add(producto)
        
        db.session.commit()
        print("Productos iniciales creados")


# Decorador para requerir login en rutas administrativas
def login_required(f):
    """
    Decorador que protege las rutas administrativas.
    Si el usuario no está logueado, lo redirige al login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# Función auxiliar para obtener la hora actual en Cuba
def obtener_hora_cuba():
    """Retorna la hora actual en la zona horaria de Cuba"""
    return datetime.now(cuba_tz)


# Función para enviar mensaje por WhatsApp
def enviar_whatsapp(mensaje):
    """
    Envía un mensaje a WhatsApp usando la API de CallMeBot.
    Retorna True si fue exitoso, False en caso contrario.
    """
    phone = app.config['WHATSAPP_PHONE']
    apikey = app.config['CALLMEBOT_API_KEY']
    
    # Codificar el mensaje para URL
    mensaje_codificado = quote(mensaje)
    
    # Construir la URL de la API
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={mensaje_codificado}&apikey={apikey}"
    
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error al enviar WhatsApp: {e}")
        return False


# Función para obtener el siguiente número de pedido
def obtener_siguiente_numero_pedido():
    """
    Obtiene el siguiente número de pedido único.
    Comienza en 1281 según la especificación.
    """
    ultimo_pedido = Pedido.query.order_by(Pedido.numero_pedido.desc()).first()
    if ultimo_pedido:
        return ultimo_pedido.numero_pedido + 1
    return app.config['INITIAL_ORDER_NUMBER']  # 1281


# Función para calcular el costo de mensajería
def calcular_costo_mensajeria(municipio, zona):
    """
    Calcula el costo de mensajería basado en el municipio y zona.
    Retorna el costo en CUP o None si no se encuentra.
    """
    costos = app.config['DELIVERY_COSTS']
    
    if municipio in costos:
        zonas = costos[municipio]
        
        # Algunos municipios tienen costo único para todas las zonas
        if 'Todo' in zonas:
            return zonas['Todo']
        elif 'todas' in zonas:
            return zonas['todas']
        
        # Buscar la zona específica
        if zona in zonas:
            costo = zonas[zona]
            # Si el costo es "NO", significa que no hacemos envíos ahí
            if costo == "NO":
                return None
            return costo
    
    return None


# RUTAS PÚBLICAS (TIENDA)

@app.route('/')
def index():
    """Página de inicio de la tienda"""
    return render_template('index.html')


@app.route('/catalogo')
def catalogo():
    """Página del catálogo de productos"""
    # Obtener todos los productos disponibles
    productos = Producto.query.filter_by(disponible=True).all()
    
    # Organizar productos por tipo para mostrarlos mejor
    productos_por_tipo = {
        'oscuro': [],
        'leche': [],
        'blanco': []
    }
    
    for producto in productos:
        productos_por_tipo[producto.tipo_chocolate].append(producto)
    
    return render_template('catalogo.html', productos_por_tipo=productos_por_tipo)


@app.route('/api/calcular-mensajeria', methods=['POST'])
def api_calcular_mensajeria():
    """
    API endpoint para calcular el costo de mensajería.
    Usado por JavaScript para actualizar el costo en tiempo real.
    """
    data = request.get_json()
    municipio = data.get('municipio')
    zona = data.get('zona')
    
    costo = calcular_costo_mensajeria(municipio, zona)
    
    if costo is None:
        return jsonify({
            'success': False,
            'message': 'No realizamos envíos a esta zona. Podemos coordinar un punto de encuentro cercano.'
        })
    
    return jsonify({
        'success': True,
        'costo': costo
    })


@app.route('/api/municipios-zonas', methods=['GET'])
def api_municipios_zonas():
    """
    API endpoint que retorna la estructura de municipios y zonas disponibles.
    Usado para poblar los selectores en el formulario.
    """
    return jsonify(app.config['DELIVERY_COSTS'])


@app.route('/realizar-pedido', methods=['POST'])
def realizar_pedido():
    """
    Procesa el formulario de pedido y crea un nuevo pedido en la base de datos.
    Envía la notificación por WhatsApp al dueño.
    """
    try:
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        municipio = request.form.get('municipio')
        zona = request.form.get('zona')
        fecha_entrega = request.form.get('fecha_entrega')
        horario_entrega = request.form.get('horario_entrega')
        observaciones = request.form.get('observaciones', '')
        
        # Productos seleccionados
        productos_seleccionados = request.form.getlist('productos')  # Lista de IDs de productos
        cantidades = {}
        for producto_id in productos_seleccionados:
            cantidad = request.form.get(f'cantidad_{producto_id}')
            if cantidad:
                cantidades[int(producto_id)] = int(cantidad)
        
        # Extras
        incluye_bolsa = request.form.get('bolsa_regalo') == 'on'
        incluye_tarjeta = request.form.get('tarjeta') == 'on'
        
        # Validar que hay al menos un producto
        if not cantidades:
            flash('Debes seleccionar al menos un producto', 'error')
            return redirect(url_for('catalogo'))
        
        # Buscar o crear cliente
        cliente = Cliente.query.filter_by(telefono=telefono).first()
        if not cliente:
            cliente = Cliente(
                nombre=nombre,
                telefono=telefono,
                direccion=direccion,
                municipio=municipio,
                zona=zona
            )
            db.session.add(cliente)
            db.session.flush()  # Para obtener el ID sin hacer commit
        
        # Calcular costo de mensajería
        costo_mensajeria = calcular_costo_mensajeria(municipio, zona)
        if costo_mensajeria is None:
            costo_mensajeria = 0  # Punto de encuentro
        
        # Crear el pedido
        pedido = Pedido(
            numero_pedido=obtener_siguiente_numero_pedido(),
            cliente_id=cliente.id,
            fecha_entrega=datetime.strptime(fecha_entrega, '%Y-%m-%d').date(),
            horario_entrega=horario_entrega,
            direccion_entrega=direccion,
            municipio_entrega=municipio,
            zona_entrega=zona,
            costo_mensajeria=costo_mensajeria,
            incluye_bolsa_regalo=incluye_bolsa,
            incluye_tarjeta=incluye_tarjeta,
            observaciones=observaciones
        )
        
        db.session.add(pedido)
        db.session.flush()
        
        # Agregar los productos al pedido
        for producto_id, cantidad in cantidades.items():
            producto = Producto.query.get(producto_id)
            if producto and producto.disponible:
                item = ItemPedido(
                    pedido_id=pedido.id,
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unitario=producto.precio
                )
                item.calcular_precio_total()
                db.session.add(item)
        
        # Calcular totales
        pedido.calcular_totales()
        
        # Guardar todo en la base de datos
        db.session.commit()
        
        # Enviar notificación por WhatsApp
        mensaje_whatsapp = pedido.generar_mensaje_whatsapp()
        whatsapp_enviado = enviar_whatsapp(mensaje_whatsapp)
        
        if not whatsapp_enviado:
            flash('Pedido creado pero hubo un problema al enviar la notificación. Por favor contacta directamente.', 'warning')
        
        # Redirigir a página de confirmación
        return redirect(url_for('confirmacion', pedido_id=pedido.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear pedido: {e}")
        flash('Hubo un error al procesar tu pedido. Por favor intenta de nuevo.', 'error')
        return redirect(url_for('catalogo'))


@app.route('/confirmacion/<int:pedido_id>')
def confirmacion(pedido_id):
    """Página de confirmación del pedido"""
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template('confirmacion.html', pedido=pedido)


# RUTAS ADMINISTRATIVAS

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login para el panel administrativo"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(username=username, activo=True).first()
        
        if usuario and usuario.check_password(password):
            # Login exitoso
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            session.permanent = True  # La sesión dura según PERMANENT_SESSION_LIFETIME
            
            # Actualizar último acceso
            usuario.ultimo_acceso = obtener_hora_cuba()
            db.session.commit()
            
            flash('Bienvenido al panel de administración', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Cerrar sesión administrativa"""
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('index'))


@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Panel principal de administración con estadísticas generales"""
    hoy = obtener_hora_cuba().date()
    
    # Estadísticas del día
    pedidos_hoy = Pedido.query.filter(
        db.func.date(Pedido.fecha_pedido) == hoy
    ).all()
    
    # Calcular totales del día
    ventas_hoy = sum(p.total for p in pedidos_hoy)
    pedidos_pendientes = Pedido.query.filter_by(estado='PENDIENTE').count()
    
    # Pedidos para mañana
    manana = hoy + timedelta(days=1)
    pedidos_manana = Pedido.query.filter_by(
        fecha_entrega=manana,
        estado='PENDIENTE'
    ).all()
    
    # Productos más vendidos del mes
    inicio_mes = hoy.replace(day=1)
    productos_populares = db.session.query(
        Producto.nombre,
        Producto.tipo_chocolate,
        db.func.sum(ItemPedido.cantidad).label('total_vendido')
    ).join(ItemPedido).join(Pedido).filter(
        Pedido.fecha_pedido >= inicio_mes,
        Pedido.estado != 'CANCELADO'
    ).group_by(Producto.id).order_by(db.desc('total_vendido')).limit(5).all()
    
    return render_template('admin/dashboard.html',
        ventas_hoy=ventas_hoy,
        pedidos_hoy=len(pedidos_hoy),
        pedidos_pendientes=pedidos_pendientes,
        pedidos_manana=pedidos_manana,
        productos_populares=productos_populares
    )


@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    """Gestión de pedidos"""
    # Obtener filtros de la URL
    estado = request.args.get('estado', 'todos')
    fecha = request.args.get('fecha', '')
    
    # Consulta base
    query = Pedido.query
    
    # Aplicar filtros
    if estado != 'todos':
        query = query.filter_by(estado=estado.upper())
    
    if fecha:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        query = query.filter(db.func.date(Pedido.fecha_entrega) == fecha_obj)
    
    # Ordenar por fecha de pedido descendente
    pedidos = query.order_by(Pedido.fecha_pedido.desc()).all()
    
    return render_template('admin/pedidos.html', pedidos=pedidos, estado_filtro=estado, fecha_filtro=fecha)


@app.route('/admin/pedidos/<int:pedido_id>/cambiar-estado', methods=['POST'])
@login_required
def cambiar_estado_pedido(pedido_id):
    """Cambiar el estado de un pedido"""
    pedido = Pedido.query.get_or_404(pedido_id)
    nuevo_estado = request.form.get('estado')
    
    if nuevo_estado in ['PENDIENTE', 'COMPLETADO', 'CANCELADO']:
        estado_anterior = pedido.estado
        pedido.estado = nuevo_estado
        
        # Si se completa el pedido, registrar las transacciones
        if nuevo_estado == 'COMPLETADO' and estado_anterior != 'COMPLETADO':
            # Registrar venta
            transaccion_venta = Transaccion(
                tipo_transaccion='VENTA',
                concepto=f'Venta pedido #{pedido.numero_pedido}',
                monto=pedido.total,
                pedido_id=pedido.id,
                registrado_por=session.get('username')
            )
            db.session.add(transaccion_venta)
            
            # Calcular y registrar comisiones si hay trabajadores asignados
            if pedido.gestor_id:
                comision_gestor = pedido.total * app.config['COMISION_GESTOR']
                transaccion_gestor = Transaccion(
                    tipo_transaccion='COMISION',
                    concepto=f'Comisión gestor - Pedido #{pedido.numero_pedido}',
                    monto=comision_gestor,
                    pedido_id=pedido.id,
                    trabajador_id=pedido.gestor_id,
                    registrado_por=session.get('username')
                )
                db.session.add(transaccion_gestor)
                
                # Actualizar total ganado del trabajador
                gestor = Trabajador.query.get(pedido.gestor_id)
                gestor.total_ganado += comision_gestor
                gestor.pedidos_completados += 1
            
            # Similar para mensajero y elaborador...
            
            # Registrar ganancia del negocio
            ganancia_negocio = pedido.total * app.config['MARGEN_NEGOCIO']
            transaccion_negocio = Transaccion(
                tipo_transaccion='GANANCIA_NEGOCIO',
                concepto=f'Ganancia negocio - Pedido #{pedido.numero_pedido}',
                monto=ganancia_negocio,
                pedido_id=pedido.id,
                registrado_por=session.get('username')
            )
            db.session.add(transaccion_negocio)
        
        db.session.commit()
        flash(f'Estado del pedido #{pedido.numero_pedido} cambiado a {nuevo_estado}', 'success')
    
    return redirect(url_for('admin_pedidos'))


@app.route('/admin/pedidos/<int:pedido_id>/asignar-trabajadores', methods=['POST'])
@login_required
def asignar_trabajadores(pedido_id):
    """Asignar trabajadores a un pedido"""
    pedido = Pedido.query.get_or_404(pedido_id)
    
    pedido.gestor_id = request.form.get('gestor_id') or None
    pedido.mensajero_id = request.form.get('mensajero_id') or None
    pedido.elaborador_id = request.form.get('elaborador_id') or None
    
    db.session.commit()
    flash('Trabajadores asignados correctamente', 'success')
    
    return redirect(url_for('admin_pedidos'))


@app.route('/admin/pedidos/resumen-dia')
@login_required
def resumen_pedidos_dia():
    """Muestra un resumen de los pedidos para un día específico"""
    fecha = request.args.get('fecha')
    if not fecha:
        fecha = (obtener_hora_cuba().date() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    # Obtener todos los pedidos para esa fecha
    pedidos = Pedido.query.filter_by(
        fecha_entrega=fecha_obj,
        estado='PENDIENTE'
    ).all()
    
    # Contar productos necesarios
    productos_necesarios = {}
    for pedido in pedidos:
        for item in pedido.items:
            key = f"{item.producto.nombre} - {item.producto.tamano}"
            if key not in productos_necesarios:
                productos_necesarios[key] = 0
            productos_necesarios[key] += item.cantidad
    
    return render_template('admin/resumen_dia.html',
        fecha=fecha,
        pedidos=pedidos,
        productos_necesarios=productos_necesarios
    )


@app.route('/admin/finanzas')
@login_required
def admin_finanzas():
    """Panel de gestión financiera"""
    # Obtener rango de fechas
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    if not fecha_inicio:
        fecha_inicio = obtener_hora_cuba().date().replace(day=1)  # Primer día del mes
    else:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    
    if not fecha_fin:
        fecha_fin = obtener_hora_cuba().date()
    else:
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    
    # Obtener todas las transacciones en el rango
    transacciones = Transaccion.query.filter(
        db.func.date(Transaccion.fecha) >= fecha_inicio,
        db.func.date(Transaccion.fecha) <= fecha_fin
    ).all()
    
    # Calcular totales por tipo
    totales = {
        'ventas': 0,
        'comisiones_gestor': 0,
        'comisiones_mensajero': 0,
        'comisiones_elaborador': 0,
        'ganancias_negocio': 0,
        'gastos': 0
    }
    
    for t in transacciones:
        if t.tipo_transaccion == 'VENTA':
            totales['ventas'] += t.monto
        elif t.tipo_transaccion == 'COMISION':
            if t.trabajador:
                if t.trabajador.tipo == 'GESTOR':
                    totales['comisiones_gestor'] += t.monto
                elif t.trabajador.tipo == 'MENSAJERO':
                    totales['comisiones_mensajero'] += t.monto
                elif t.trabajador.tipo == 'ELABORADOR':
                    totales['comisiones_elaborador'] += t.monto
        elif t.tipo_transaccion == 'GANANCIA_NEGOCIO':
            totales['ganancias_negocio'] += t.monto
        elif t.tipo_transaccion == 'GASTO':
            totales['gastos'] += t.monto
    
    return render_template('admin/finanzas.html',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        transacciones=transacciones,
        totales=totales
    )


@app.route('/admin/trabajadores')
@login_required
def admin_trabajadores():
    """Gestión de trabajadores"""
    trabajadores = Trabajador.query.all()
    return render_template('admin/trabajadores.html', trabajadores=trabajadores)


@app.route('/admin/trabajadores/crear', methods=['POST'])
@login_required
def crear_trabajador():
    """Crear un nuevo trabajador"""
    trabajador = Trabajador(
        nombre=request.form.get('nombre'),
        tipo=request.form.get('tipo'),
        telefono=request.form.get('telefono'),
        email=request.form.get('email'),
        activo=True
    )
    
    db.session.add(trabajador)
    db.session.commit()
    
    flash(f'Trabajador {trabajador.nombre} creado correctamente', 'success')
    return redirect(url_for('admin_trabajadores'))


@app.route('/admin/trabajadores/<int:trabajador_id>/toggle-activo', methods=['POST'])
@login_required
def toggle_trabajador_activo(trabajador_id):
    """Activar/desactivar un trabajador"""
    trabajador = Trabajador.query.get_or_404(trabajador_id)
    trabajador.activo = not trabajador.activo
    db.session.commit()
    
    estado = 'activado' if trabajador.activo else 'desactivado'
    flash(f'Trabajador {trabajador.nombre} {estado}', 'success')
    
    return redirect(url_for('admin_trabajadores'))


@app.route('/admin/estadisticas')
@login_required
def admin_estadisticas():
    """Panel de estadísticas avanzadas"""
    # Aquí irían las estadísticas mensuales, anuales, etc.
    # Similar a finanzas pero con vista más amplia
    return render_template('admin/estadisticas.html')


@app.route('/admin/tienda')
@login_required
def admin_tienda():
    """Configuración de la tienda"""
    productos = Producto.query.all()
    configuraciones = ConfiguracionTienda.query.all()
    return render_template('admin/tienda.html', productos=productos, configuraciones=configuraciones)


@app.route('/admin/productos/<int:producto_id>/toggle-disponible', methods=['POST'])
@login_required
def toggle_producto_disponible(producto_id):
    """Activar/desactivar disponibilidad de un producto"""
    producto = Producto.query.get_or_404(producto_id)
    producto.disponible = not producto.disponible
    db.session.commit()
    
    estado = 'disponible' if producto.disponible else 'no disponible'
    flash(f'Producto {producto.nombre} marcado como {estado}', 'success')
    
    return redirect(url_for('admin_tienda'))


# Manejadores de errores
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


# Contexto global para las plantillas
@app.context_processor
def inject_globals():
    """Inyecta variables globales a todas las plantillas"""
    return dict(
        business_name=app.config['BUSINESS_NAME'],
        currency=app.config['CURRENCY'],
        facebook_url=app.config['FACEBOOK_URL'],
        instagram_url=app.config['INSTAGRAM_URL']
    )


# Punto de entrada de la aplicación
if __name__ == '__main__':
    # En desarrollo
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # En producción (Railway detectará esto automáticamente)
    pass
