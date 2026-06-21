"""微信登录接口"""
import logging
from flask import Blueprint, request, jsonify
import httpx
from database import get_db
from config import Config

logger = logging.getLogger(__name__)
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

    # 调用微信 code2session（timeout 5 秒，iOS 端总超时通常 ~10s，留一半给数据库和网络往返）
    wx_url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': Config.WX_APPID,
        'secret': Config.WX_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    try:
        resp = httpx.get(wx_url, params=params, timeout=5.0)
        resp.raise_for_status()
        wx_data = resp.json()
    except httpx.TimeoutException:
        logger.warning("微信 code2session 超时 (5s)")
        return jsonify({'code': 503, 'message': '微信服务响应超时，请重试'}), 503
    except httpx.HTTPStatusError as e:
        logger.error(f"微信 code2session HTTP 错误: {e.response.status_code}")
        return jsonify({'code': 502, 'message': '微信服务异常，请稍后重试'}), 502
    except Exception as e:
        logger.error(f"微信 code2session 调用失败: {e}")
        return jsonify({'code': 502, 'message': '微信服务不可达，请稍后重试'}), 502

    openid = wx_data.get('openid')
    if not openid:
        errmsg = wx_data.get('errmsg', '')
        logger.warning(f"微信返回错误: errcode={wx_data.get('errcode')}, errmsg={errmsg}")
        return jsonify({'code': 401, 'message': '微信登录失败: ' + errmsg}), 401

    logger.info(f"用户登录: openid={openid}")

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
        logger.info(f"新用户注册: openid={openid}")

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
