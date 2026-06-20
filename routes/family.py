"""家庭管理接口"""
from flask import Blueprint, request, jsonify
import secrets
import string
import json
import os
import uuid
from datetime import datetime
from database import get_db

family_bp = Blueprint('family', __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_family_id():
    """生成 8 位家庭码"""
    chars = string.ascii_lowercase + string.digits
    return 'fam-' + ''.join(secrets.choice(chars) for _ in range(8))


def resolve_member_info(db, openid, family_id):
    """根据 openid + family_id 解析昵称和头像（优先 permissions 中的自定义值，否则用 users 表）"""
    # 从 family permissions 里查
    fam = db.execute('SELECT permissions FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if fam and fam['permissions']:
        try:
            perms = json.loads(fam['permissions'])
            entry = perms.get(openid)
            if entry:
                return entry.get('nickname', ''), entry.get('avatar_url', '')
        except:
            pass
    # fallback: users 表
    user = db.execute('SELECT nickname, avatar_url FROM users WHERE openid = ?', (openid,)).fetchone()
    if user:
        return user['nickname'] or '', user['avatar_url'] or ''
    return '', ''


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
    now = datetime.now().isoformat()

    # 初始化 babies 数组：将主宝宝也加入
    main_baby_id = 'baby-' + str(uuid.uuid4())[:8]
    babies = [{
        'id': main_baby_id,
        'name': baby_name,
        'birthday': baby_birthday,
        'gender': '',
        'avatar': baby_avatar
    }]
    permissions = {
        openid: {
            'role': role,
            'nickname': '',
            'avatar_url': ''
        }
    }

    db.execute(
        'INSERT INTO families (family_id, baby_name, baby_birthday, baby_avatar, created_by, created_at, babies, permissions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (family_id, baby_name, baby_birthday, baby_avatar, openid, now, json.dumps(babies), json.dumps(permissions))
    )
    db.execute(
        'INSERT INTO family_members (family_id, openid, role) VALUES (?, ?, ?)',
        (family_id, openid, role)
    )
    db.commit()

    return jsonify({
        'code': 0,
        'data': {'familyId': family_id, 'babyName': baby_name, 'role': role, 'babies': babies}
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

    # 更新 permissions JSON
    perms = {}
    if family['permissions']:
        try:
            perms = json.loads(family['permissions'])
        except:
            perms = {}
    user = db.execute('SELECT nickname, avatar_url FROM users WHERE openid = ?', (openid,)).fetchone()
    perms[openid] = {
        'role': role,
        'nickname': user['nickname'] if user else '',
        'avatar_url': user['avatar_url'] if user else ''
    }
    db.execute('UPDATE families SET permissions = ? WHERE family_id = ?',
               (json.dumps(perms), family_id))

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

    # 解析权限：补充自定义昵称/头像
    perms = {}
    if family['permissions']:
        try:
            perms = json.loads(family['permissions'])
        except:
            perms = {}

    members_out = []
    for m in members:
        entry = dict(m)
        p = perms.get(m['openid'], {})
        # 若权限中有自定义值，覆盖 users 表的默认值
        if p.get('nickname'):
            entry['nickname'] = p['nickname']
        if p.get('avatar_url'):
            entry['avatar_url'] = p['avatar_url']
        members_out.append(entry)

    # 解析 babies
    babies = []
    if family['babies']:
        try:
            babies = json.loads(family['babies'])
        except:
            babies = []

    return jsonify({
        'code': 0,
        'data': {
            'familyId': member['family_id'],
            'babyName': family['baby_name'],
            'babyBirthday': family['baby_birthday'],
            'babyAvatar': family['baby_avatar'],
            'babies': babies,
            'myRole': member['role'],
            'permissions': perms,
            'members': members_out
        }
    })


# ========== 宝宝管理 ==========

@family_bp.route('/api/family/babies', methods=['GET'])
def get_babies():
    """获取宝宝列表"""
    family_id = request.args.get('family_id', '')
    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    family = db.execute('SELECT babies FROM families WHERE family_id = ?', (family_id,)).fetchone()
    db.close()
    if not family:
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    babies = []
    if family['babies']:
        try:
            babies = json.loads(family['babies'])
        except:
            babies = []

    return jsonify({'code': 0, 'data': babies, 'message': 'ok'})


@family_bp.route('/api/family/baby', methods=['POST'])
def add_baby():
    """添加宝宝"""
    data = request.get_json()
    family_id = data.get('family_id', '')
    name = data.get('name', '宝宝')
    birthday = data.get('birthday', '')
    gender = data.get('gender', '')
    avatar = data.get('avatar', '')

    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    family = db.execute('SELECT babies FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if not family:
        db.close()
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    babies = []
    if family['babies']:
        try:
            babies = json.loads(family['babies'])
        except:
            babies = []

    baby_id = 'baby-' + str(uuid.uuid4())[:8]
    new_baby = {
        'id': baby_id,
        'name': name,
        'birthday': birthday,
        'gender': gender,
        'avatar': avatar
    }
    babies.append(new_baby)

    db.execute('UPDATE families SET babies = ? WHERE family_id = ?',
               (json.dumps(babies), family_id))
    db.commit()
    db.close()

    return jsonify({'code': 0, 'data': new_baby, 'message': '宝宝添加成功'})


@family_bp.route('/api/family/baby/<baby_id>', methods=['PUT'])
def update_baby(baby_id):
    """修改宝宝信息"""
    data = request.get_json()
    family_id = data.get('family_id', '')

    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    family = db.execute('SELECT babies FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if not family:
        db.close()
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    babies = []
    if family['babies']:
        try:
            babies = json.loads(family['babies'])
        except:
            babies = []

    updated = None
    for b in babies:
        if b['id'] == baby_id:
            b['name'] = data.get('name', b['name'])
            b['birthday'] = data.get('birthday', b['birthday'])
            b['gender'] = data.get('gender', b['gender'])
            b['avatar'] = data.get('avatar', b['avatar'])
            updated = b
            break

    if not updated:
        db.close()
        return jsonify({'code': 404, 'message': '宝宝不存在'}), 404

    db.execute('UPDATE families SET babies = ? WHERE family_id = ?',
               (json.dumps(babies), family_id))
    db.commit()
    db.close()

    return jsonify({'code': 0, 'data': updated, 'message': '宝宝信息已更新'})


@family_bp.route('/api/family/baby/<baby_id>', methods=['DELETE'])
def delete_baby(baby_id):
    """删除宝宝"""
    family_id = request.args.get('family_id', '')

    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    family = db.execute('SELECT babies FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if not family:
        db.close()
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    babies = []
    if family['babies']:
        try:
            babies = json.loads(family['babies'])
        except:
            babies = []

    if len(babies) <= 1:
        db.close()
        return jsonify({'code': 400, 'message': '至少保留一个宝宝'}), 400

    new_babies = [b for b in babies if b['id'] != baby_id]
    if len(new_babies) == len(babies):
        db.close()
        return jsonify({'code': 404, 'message': '宝宝不存在'}), 404

    db.execute('UPDATE families SET babies = ? WHERE family_id = ?',
               (json.dumps(new_babies), family_id))
    db.commit()
    db.close()

    return jsonify({'code': 0, 'message': '宝宝已删除'})


# ========== 权限管理 ==========

@family_bp.route('/api/family/permissions', methods=['GET'])
def get_permissions():
    """获取家庭权限列表"""
    family_id = request.args.get('family_id', '')
    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    family = db.execute('SELECT permissions FROM families WHERE family_id = ?', (family_id,)).fetchone()
    db.close()
    if not family:
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    perms = {}
    if family['permissions']:
        try:
            perms = json.loads(family['permissions'])
        except:
            perms = {}

    return jsonify({'code': 0, 'data': perms, 'message': 'ok'})


@family_bp.route('/api/family/permissions', methods=['PUT'])
def update_permissions():
    """修改成员权限（仅管理员可操作）"""
    data = request.get_json()
    family_id = data.get('family_id', '')
    target_openid = data.get('openid', '')
    role = data.get('role', '')
    nickname = data.get('nickname', None)
    avatar_url = data.get('avatar_url', None)
    operator_openid = data.get('operator_openid', '')

    if not family_id or not target_openid:
        return jsonify({'code': 400, 'message': '缺少参数'}), 400

    db = get_db()
    family = db.execute('SELECT permissions FROM families WHERE family_id = ?', (family_id,)).fetchone()
    if not family:
        db.close()
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    perms = {}
    if family['permissions']:
        try:
            perms = json.loads(family['permissions'])
        except:
            perms = {}

    # 权限校验：仅 admin 可改他人权限
    if operator_openid and operator_openid != target_openid:
        op_entry = perms.get(operator_openid, {})
        if op_entry.get('role') != 'admin':
            db.close()
            return jsonify({'code': 403, 'message': '仅管理员可修改他人权限'}), 403

    if target_openid not in perms:
        perms[target_openid] = {'role': 'editor', 'nickname': '', 'avatar_url': ''}

    if role:
        if role not in ('admin', 'editor', 'viewer'):
            db.close()
            return jsonify({'code': 400, 'message': '无效的角色: ' + role}), 400
        perms[target_openid]['role'] = role
    if nickname is not None:
        perms[target_openid]['nickname'] = nickname
    if avatar_url is not None:
        perms[target_openid]['avatar_url'] = avatar_url

    db.execute('UPDATE families SET permissions = ? WHERE family_id = ?',
               (json.dumps(perms), family_id))
    db.commit()
    db.close()

    return jsonify({'code': 0, 'data': perms[target_openid], 'message': '权限已更新'})


# ========== 头像上传 ==========

@family_bp.route('/api/family/avatar', methods=['POST'])
def upload_avatar():
    """上传头像（返回 URL）"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'message': '未选择文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 400, 'message': '文件名为空'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        return jsonify({'code': 400, 'message': '不支持的图片格式'}), 400

    filename = 'avatar_' + str(uuid.uuid4())[:12] + '.' + ext
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    # 返回相对路径作为 URL
    url = '/static/uploads/' + filename
    return jsonify({'code': 0, 'data': {'url': url}, 'message': '上传成功'})


# ========== 家庭动态时间线 ==========

@family_bp.route('/api/family/timeline', methods=['GET'])
def get_timeline():
    """获取家庭动态时间线（最近 50 条各类型记录）"""
    family_id = request.args.get('family_id', '')
    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()
    events = []

    tables = [
        ('feeding', 'start_time', '喂奶'),
        ('sleep', 'start_time', '睡眠'),
        ('diaper', 'time', '尿布'),
        ('growth', 'record_date', '成长记录'),
        ('vaccination', 'scheduled_date', '疫苗接种'),
        ('medication', 'start_time', '用药记录'),
        ('notes', 'time', '随手记'),
    ]

    for table_name, time_col, label in tables:
        rows = db.execute(
            'SELECT *, "' + label + '" as event_type FROM ' + table_name +
            ' WHERE family_id = ? ORDER BY ' + time_col + ' DESC LIMIT 15',
            (family_id,)
        ).fetchall()
        for r in rows:
            events.append(dict(r))

    # 按时间排序取最近 50 条
    def get_ts(e):
        t = e.get('start_time') or e.get('time') or e.get('record_date') or e.get('scheduled_date') or ''
        return t

    events.sort(key=get_ts, reverse=True)
    events = events[:50]
    db.close()

    return jsonify({'code': 0, 'data': events, 'message': 'ok'})
