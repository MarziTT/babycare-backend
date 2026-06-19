"""家庭管理接口"""
from flask import Blueprint, request, jsonify
import secrets
import string
from database import get_db

family_bp = Blueprint('family', __name__)


def generate_family_id():
    """生成 8 位家庭码"""
    chars = string.ascii_lowercase + string.digits
    return 'fam-' + ''.join(secrets.choice(chars) for _ in range(8))


@family_bp.route('/api/family/create', methods=['POST'])
def create_family():
    """创建家庭"""
    data = request.get_json()
    openid = data.get('openid', '')
    baby_name = data.get('babyName', '宝宝')
    baby_birthday = data.get('babyBirthday', '')
    baby_avatar = data.get('babyAvatar', '')
    role = data.get('role', 'mom')  # 创建者角色

    if not openid:
        return jsonify({'code': 400, 'message': '缺少用户标识'}), 400

    db = get_db()
    family_id = generate_family_id()

    db.execute(
        'INSERT INTO families (family_id, baby_name, baby_birthday, baby_avatar, created_by) VALUES (?, ?, ?, ?, ?)',
        (family_id, baby_name, baby_birthday, baby_avatar, openid)
    )
    db.execute(
        'INSERT INTO family_members (family_id, openid, role) VALUES (?, ?, ?)',
        (family_id, openid, role)
    )
    db.commit()

    return jsonify({
        'code': 0,
        'data': {'familyId': family_id, 'babyName': baby_name, 'role': role}
    })


@family_bp.route('/api/family/join', methods=['POST'])
def join_family():
    """加入家庭"""
    data = request.get_json()
    openid = data.get('openid', '')
    family_id = data.get('familyId', '')
    role = data.get('role', 'other')

    if not openid or not family_id:
        return jsonify({'code': 400, 'message': '缺少参数'}), 400

    db = get_db()
    family = db.execute('SELECT * FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if not family:
        return jsonify({'code': 404, 'message': '家庭不存在，请检查家庭码'}), 404

    # 检查是否已加入
    existing = db.execute(
        'SELECT * FROM family_members WHERE family_id = ? AND openid = ?',
        (family_id, openid)
    ).fetchone()
    if existing:
        return jsonify({'code': 409, 'message': '你已在这个家庭中'}), 409

    db.execute(
        'INSERT INTO family_members (family_id, openid, role) VALUES (?, ?, ?)',
        (family_id, openid, role)
    )
    db.commit()

    return jsonify({
        'code': 0,
        'data': {
            'familyId': family_id,
            'babyName': family['baby_name'],
            'babyBirthday': family['baby_birthday'],
            'role': role
        }
    })


@family_bp.route('/api/family/members', methods=['GET'])
def get_members():
    """获取家庭成员列表"""
    openid = request.args.get('openid', '')

    db = get_db()
    # 先查出用户所属家庭
    member = db.execute(
        'SELECT family_id, role FROM family_members WHERE openid = ?',
        (openid,)
    ).fetchone()
    if not member:
        return jsonify({'code': 404, 'message': '你还未加入任何家庭'}), 404

    family = db.execute(
        'SELECT * FROM families WHERE family_id = ?',
        (member['family_id'],)
    ).fetchone()

    members = db.execute('''
        SELECT u.nickname, u.avatar_url, fm.role, fm.openid, fm.joined_at
        FROM family_members fm
        JOIN users u ON fm.openid = u.openid
        WHERE fm.family_id = ?
        ORDER BY fm.joined_at ASC
    ''', (member['family_id'],)).fetchall()

    return jsonify({
        'code': 0,
        'data': {
            'familyId': member['family_id'],
            'babyName': family['baby_name'],
            'babyBirthday': family['baby_birthday'],
            'babyAvatar': family['baby_avatar'],
            'myRole': member['role'],
            'members': [dict(m) for m in members]
        }
    })
