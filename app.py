import os
import datetime
import requests
from datetime import date, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# ------------------------------
# Configuración
# ------------------------------
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "clave_insegura")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///ventas.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------------------------
# Modelos
# ------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_cliente = db.Column(db.String(100), nullable=False)
    numero_cliente = db.Column(db.String(20))
    correo_cliente = db.Column(db.String(100))
    medio_pago = db.Column(db.String(50))
    estado_pago = db.Column(db.String(20))
    servicio = db.Column(db.String(100))
    cuenta_asociada = db.Column(db.String(100))
    contraseña = db.Column(db.String(200))
    dinero = db.Column(db.Float)
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)
    admin_pago = db.Column(db.String(50))

# ------------------------------
# Gestión de usuarios
# ------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------------------
# Funciones auxiliares
# ------------------------------
def enviar_alerta_telegram(mensaje):
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")

    if not TOKEN or not CHAT_IDS:
        print("⚠️ Telegram no configurado")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            requests.post(url, data={"chat_id": chat_id, "text": mensaje})
        except Exception as e:
            print(f"Error enviando a {chat_id}: {e}")

def revisar_vencimientos():
    with app.app_context():
        hoy = date.today()
        mañana = hoy + timedelta(days=1)
        ventas = Venta.query.filter(Venta.fecha_fin.in_([hoy, mañana])).all()
        if ventas:
            lineas = [f"- {v.servicio} ({v.nombre_cliente}) vence el {v.fecha_fin}" for v in ventas]
            body = "🔔 Recordatorio de vencimientos:\n" + "\n".join(lineas)
            enviar_alerta_telegram(body)

# ------------------------------
# Rutas
# ------------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Usuario o contraseña incorrectos")
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    ventas = Venta.query.all()
    total_ingresos = sum(v.dinero for v in ventas if v.dinero)
    return render_template('dashboard.html', ventas=ventas, total_ingresos=total_ingresos)

@app.route('/nueva', methods=['GET','POST'])
@login_required
def nueva_venta():
    if request.method == 'POST':
        fecha_inicio = request.form['fecha_inicio']
        fecha_fin = request.form['fecha_fin']
        if not fecha_inicio or not fecha_fin:
            flash("❌ Las fechas son obligatorias")
            return redirect(url_for('nueva_venta'))

        venta = Venta(
            nombre_cliente=request.form['nombre_cliente'],
            numero_cliente=request.form['numero_cliente'],
            correo_cliente=request.form['correo_cliente'],
            medio_pago=request.form['medio_pago'],
            estado_pago=request.form['estado_pago'],
            servicio=request.form['servicio'],
            cuenta_asociada=request.form['cuenta_asociada'],
            contraseña=request.form['contraseña'],
            dinero=float(request.form['dinero']) if request.form['dinero'] else 0.0,
            fecha_inicio=datetime.datetime.strptime(fecha_inicio, "%Y-%m-%d"),
            fecha_fin=datetime.datetime.strptime(fecha_fin, "%Y-%m-%d"),
            admin_pago=request.form['admin_pago']
        )
        db.session.add(venta)
        db.session.commit()
        flash("Venta registrada con éxito")
        return redirect(url_for('dashboard'))
    return render_template('nueva_venta.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
    if request.method == 'POST':
        fecha_inicio = request.form['fecha_inicio']
        fecha_fin = request.form['fecha_fin']
        if not fecha_inicio or not fecha_fin:
            flash("❌ Las fechas son obligatorias")
            return redirect(url_for('editar_venta', id=id))

        venta.nombre_cliente = request.form['nombre_cliente']
        venta.numero_cliente = request.form['numero_cliente']
        venta.correo_cliente = request.form['correo_cliente']
        venta.medio_pago = request.form['medio_pago']
        venta.estado_pago = request.form['estado_pago']
        venta.servicio = request.form['servicio']
        venta.cuenta_asociada = request.form['cuenta_asociada']
        venta.contraseña = request.form['contraseña']
        venta.dinero = float(request.form['dinero']) if request.form['dinero'] else 0.0
        venta.fecha_inicio = datetime.datetime.strptime(fecha_inicio, "%Y-%m-%d")
        venta.fecha_fin = datetime.datetime.strptime(fecha_fin, "%Y-%m-%d")
        venta.admin_pago = request.form['admin_pago']
        db.session.commit()
        flash("Venta actualizada con éxito")
        return redirect(url_for('dashboard'))
    return render_template('editar_venta.html', venta=venta)

@app.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_venta(id):
    venta = Venta.query.get_or_404(id)
    db.session.delete(venta)
    db.session.commit()
    flash("Venta eliminada")
    return redirect(url_for('dashboard'))

# ------------------------------
# Registro de usuarios (solo admin)
# ------------------------------
@app.route('/registro', methods=['GET', 'POST'])
@login_required
def registro():
    if not current_user.is_admin:
        flash("No tienes permisos para crear usuarios ❌")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe")
            return redirect(url_for('registro'))

        nuevo = User(username=username, password=password, is_admin=False)
        db.session.add(nuevo)
        db.session.commit()
        flash("Usuario creado con éxito ✅")
        return redirect(url_for('dashboard'))
    
    return render_template('registro.html')

# ------------------------------
# Cambio de contraseña
# ------------------------------
@app.route('/cambiar_password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        actual = request.form['actual']
        nueva = request.form['nueva']
        confirmar = request.form['confirmar']

        if not check_password_hash(current_user.password, actual):
            flash("❌ La contraseña actual es incorrecta")
            return redirect(url_for('cambiar_password'))

        if nueva != confirmar:
            flash("❌ La nueva contraseña y la confirmación no coinciden")
            return redirect(url_for('cambiar_password'))

        current_user.password = generate_password_hash(nueva)
        db.session.commit()
        flash("✅ Contraseña cambiada con éxito")
        return redirect(url_for('dashboard'))

    return render_template('cambiar_password.html')

@app.route('/test-alerta')
@login_required
def test_alerta():
    revisar_vencimientos()
    flash("Se envió alerta de prueba a Telegram ✅")
    return redirect(url_for('dashboard'))

# ------------------------------
# Inicialización (Render y local)
# ------------------------------
def init_app():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            user1 = User(username="Luis", password=generate_password_hash("1234"), is_admin=True)
            user2 = User(username="Johan", password=generate_password_hash("1234"), is_admin=False)
            db.session.add_all([user1, user2])
            db.session.commit()

    scheduler = BackgroundScheduler(timezone="America/Lima")
    scheduler.add_job(revisar_vencimientos, 'cron', hour=9, minute=0)
    scheduler.start()

init_app()

if __name__ == '__main__':
    app.run(debug=True)

