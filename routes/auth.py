"""微信登录接口"""
from flask import Blueprint, request, jsonify
import httpx
from database import get_db
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """微信登录：code 换取 openid，自动注册"""
    data = request.get_json()
    code = data.get('code', '')
    nickname = data.get('nickname', '')
    avatar_url = data.get('avatarUrl', '')

    if not code:
        return jsonify({'code': 400, 'message': '缺少登录凭证'}), 400

    # 调用微信 code2session
    wx_url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': Config.WX_APPID,
        'secret': Config.WX_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    resp = httpx.get(wx_url, params=params, timeout=10)
    wx_data = resp.json()

    openid = wx_data.get('openid')
    if not openid:
        return jsonify({'code': 401, 'message': '微信登录失败: ' + wx_data.get('errmsg', '')}), 401

    db = get_db()
    # 查找或创建用户
    user = db.execute('SELECT * FROM users WHERE openid = ?', (openid,)).fetchone()
    if user is None:
        db.execute(
            'INSERT INTO users (openid, nickname, avatar_url) VALUES (?, ?, ?)',
            (openid, nickname, avatar_url)
        )
        db.commit()
        user = db.execute('SELECT * FROM users WHERE openid = ?', (openid,)).fetchone()

    # 查询该用户所在的家庭
    family = db.execute('''
        SELECT f.*, fm.role FROM families f
        JOIN family_members fm ON f.family_id = fm.family_id
        WHERE fm.openid = ?
    ''', (openid,)).fetchone()

    return jsonify({
        'code': 0,
        'data': {
            'openid': openid,
            'nickname': nickname,
            'avatarUrl': avatar_url,
            'family': dict(family) if family else None
        }
    })
