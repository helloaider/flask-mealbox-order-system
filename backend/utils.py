from functools import wraps
from flask import request, jsonify
import jwt
from config import SECRET_KEY


def _decode_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, 'missing_token'
    token = auth[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, 'token_expired'
    except jwt.InvalidTokenError:
        return None, 'invalid_token'


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return jsonify({'error': '请先登录'}), 401
        if payload.get('role') != 'student':
            return jsonify({'error': '权限不足'}), 403
        from models import User
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': '用户不存在'}), 401
        return f(user, *args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return jsonify({'error': '请先登录'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': '权限不足'}), 403
        # 验证 admin 在数据库中仍存在（防止被删后 token 仍有效）
        from models import Admin
        if not Admin.query.get(payload['user_id']):
            return jsonify({'error': '账号不存在'}), 401
        return f(*args, **kwargs)
    return decorated
