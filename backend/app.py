from flask import Flask, send_from_directory
from flask_cors import CORS
from models import db
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.orders import orders_bp
from routes.admin import admin_bp
from routes.stats import stats_bp
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', 'frontend'))
ADMIN_DIR    = os.path.normpath(os.path.join(BASE_DIR, '..', 'admin'))

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "food_order.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

app.register_blueprint(auth_bp,   url_prefix='/api/auth')
app.register_blueprint(menu_bp,   url_prefix='/api/menu')
app.register_blueprint(orders_bp, url_prefix='/api/orders')
app.register_blueprint(admin_bp,  url_prefix='/api/admin')
app.register_blueprint(stats_bp,  url_prefix='/api/admin/stats')


@app.route('/')
def student_index():
    resp = send_from_directory(FRONTEND_DIR, 'index.html')
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


@app.route('/admin')
def admin_index():
    resp = send_from_directory(ADMIN_DIR, 'index.html')
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


@app.route('/api/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 兼容旧数据库：orders 表可能没有 session_id 列
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('orders')]
        if 'session_id' not in cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE orders ADD COLUMN session_id INTEGER REFERENCES order_sessions(id)'))
                conn.commit()
            print('✅ 已自动添加 orders.session_id 列')
        if 'pickup_point_id' not in cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE orders ADD COLUMN pickup_point_id INTEGER REFERENCES pickup_points(id)'))
                conn.commit()
            print('✅ 已自动添加 orders.pickup_point_id 列')
        # 兼容旧数据库：combo_types 表可能没有 is_featured 列
        combo_cols = [c['name'] for c in inspector.get_columns('combo_types')]
        if 'is_featured' not in combo_cols:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE combo_types ADD COLUMN is_featured BOOLEAN DEFAULT 0'))
                conn.commit()
            print('✅ 已自动添加 combo_types.is_featured 列')
        # 兼容旧数据库：orders 表可能没有 payment_note 列
        if 'payment_note' not in cols:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE orders ADD COLUMN payment_note VARCHAR(100) DEFAULT ''"))
                conn.commit()
            print('✅ 已自动添加 orders.payment_note 列')
        # system_config 表由 db.create_all() 自动创建（新表）
        # 兼容旧数据库：users 表可能没有 class_name 列
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        if 'class_name' not in user_cols:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN class_name VARCHAR(50) DEFAULT ''"))
                conn.commit()
            print('✅ 已自动添加 users.class_name 列')
        from seed import seed_data
        seed_data()
    # 获取本机局域网 IP 用于提示
    import socket
    try:
        lan_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        lan_ip = '本机IP'
    print('🍱 每日盒饭 · 在线套餐点餐配送系统已启动')
    print(f'   本机访问 - 用户端: http://localhost:5001')
    print(f'   本机访问 - 管理端: http://localhost:5001/admin')
    print(f'   手机访问 - 用户端: http://{lan_ip}:5001')
    print(f'   手机访问 - 管理端: http://{lan_ip}:5001/admin')
    print(f'   （手机需与电脑在同一 WiFi）')
    app.run(debug=os.environ.get('FLASK_DEBUG', '1') == '1', host='0.0.0.0', port=5001)

