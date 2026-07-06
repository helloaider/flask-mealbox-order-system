from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from models import db, User
from config import SECRET_KEY

auth_bp = Blueprint('auth', __name__)


def make_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.datetime.now() + datetime.timedelta(days=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name       = (data.get('name')       or '').strip()
    phone      = (data.get('phone')      or '').strip()
    password   = (data.get('password')   or '')          # 密码不 strip，保留用户输入的空格
    class_name = (data.get('class_name') or '').strip()

    if not all([name, phone, password]):
        return jsonify({'error': '姓名、手机号、密码均为必填'}), 400
    if len(phone) != 11 or not phone.isdigit():
        return jsonify({'error': '请输入正确的11位手机号'}), 400
    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': '该手机号已注册'}), 400

    user = User(
        name=name,
        phone=phone,
        password_hash=generate_password_hash(password),
        class_name=class_name,
    )
    db.session.add(user)
    db.session.commit()

    token = make_token(user.id, 'student')
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    phone    = (data.get('phone')    or '').strip()
    password = (data.get('password') or '')     # 密码不 strip

    user = User.query.filter_by(phone=phone).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': '手机号或密码错误'}), 401

    token = make_token(user.id, 'student')
    return jsonify({'token': token, 'user': user.to_dict()}), 200


@auth_bp.route('/me', methods=['GET'])
def get_me():
    """获取当前用户信息"""
    from utils import _decode_token
    payload, err = _decode_token()
    if err:
        return jsonify({'error': '请先登录'}), 401
    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({'error': '用户不存在'}), 401
    return jsonify(user.to_dict())


@auth_bp.route('/me', methods=['PUT'])
def update_me():
    """更新个人信息：姓名、备注、密码"""
    from utils import _decode_token
    payload, err = _decode_token()
    if err:
        return jsonify({'error': '请先登录'}), 401
    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({'error': '用户不存在'}), 401

    data = request.get_json()
    name       = (data.get('name')       or '').strip()
    class_name = (data.get('class_name') or '').strip()
    new_pwd    = (data.get('new_password') or '')
    old_pwd    = (data.get('old_password') or '')

    if not name:
        return jsonify({'error': '姓名不能为空'}), 400

    user.name       = name
    user.class_name = class_name  # 备注为选填，空字符串也接受

    if new_pwd:
        if not old_pwd:
            return jsonify({'error': '请输入当前密码'}), 400
        if not check_password_hash(user.password_hash, old_pwd):
            return jsonify({'error': '当前密码错误'}), 400
        if len(new_pwd) < 6:
            return jsonify({'error': '新密码至少6位'}), 400
        user.password_hash = generate_password_hash(new_pwd)

    db.session.commit()
    return jsonify(user.to_dict())
