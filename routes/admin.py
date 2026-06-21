"""管理后台 API"""
from functools import wraps
from flask import Blueprint, request, jsonify
from config import Config
from database import get_db

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """管理后台认证中间件 — 通过 X-Admin-Key 请求头验证"""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-Admin-Key', '')
        if key != Config.ADMIN_KEY:
            return jsonify({'code': 401, 'message': '管理认证失败：无效的 Admin Key'}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== 统计 ====================

@admin_bp.route('/api/admin/stats', methods=['GET'])
@admin_required
def stats():
    """返回 families, babies, records, users 统计数量"""
    db = get_db()

    families_count = db.execute('SELECT COUNT(*) as cnt FROM families').fetchone()['cnt']
    users_count = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()['cnt']

    # 统计所有宝宝数：汇总 families 表 babies JSON 数组长度
    rows = db.execute('SELECT babies FROM families').fetchall()
    babies_count = 0
    import json
    for r in rows:
        if r['babies']:
            try:
                babies_count += len(json.loads(r['babies']))
            except:
                pass

    # 所有记录表的行数合计
    tables = ['feeding', 'sleep', 'diaper', 'growth', 'vaccination', 'medication', 'notes']
    records_count = 0
    for t in tables:
        row = db.execute(f'SELECT COUNT(*) as cnt FROM {t}').fetchone()
        records_count += row['cnt']

    db.close()
    return jsonify({
        'code': 0,
        'data': {
            'families': families_count,
            'babies': babies_count,
            'records': records_count,
            'users': users_count
        }
    })


# ==================== 家庭管理 ====================

@admin_bp.route('/api/admin/families', methods=['GET'])
@admin_required
def list_families():
    """家庭列表，含成员和宝宝信息"""
    db = get_db()

    families = db.execute(
        'SELECT * FROM families ORDER BY created_at DESC'
    ).fetchall()

    result = []
    import json
    for fam in families:
        fam_dict = dict(fam)

        # 解析 babies JSON
        babies = []
        if fam['babies']:
            try:
                babies = json.loads(fam['babies'])
            except:
                pass

        # 获取家庭成员
        members = db.execute('''
            SELECT fm.openid, fm.role, fm.joined_at,
                   u.nickname, u.avatar_url
            FROM family_members fm
            LEFT JOIN users u ON fm.openid = u.openid
            WHERE fm.family_id = ?
            ORDER BY fm.joined_at ASC
        ''', (fam['family_id'],)).fetchall()
        members_out = [dict(m) for m in members]

        # 获取各类型记录数
        tables = ['feeding', 'sleep', 'diaper', 'growth', 'vaccination', 'medication', 'notes']
        record_counts = {}
        for t in tables:
            row = db.execute(
                f'SELECT COUNT(*) as cnt FROM {t} WHERE family_id = ?',
                (fam['family_id'],)
            ).fetchone()
            record_counts[t] = row['cnt']

        result.append({
            'family_id': fam_dict['family_id'],
            'baby_name': fam_dict['baby_name'],
            'baby_birthday': fam_dict['baby_birthday'],
            'created_by': fam_dict['created_by'],
            'created_at': fam_dict['created_at'],
            'babies': babies,
            'members': members_out,
            'record_counts': record_counts
        })

    db.close()
    return jsonify({'code': 0, 'data': result, 'total': len(result)})


@admin_bp.route('/api/admin/families/<family_id>', methods=['DELETE'])
@admin_required
def delete_family(family_id):
    """删除指定家庭及其关联数据"""
    if not family_id:
        return jsonify({'code': 400, 'message': '缺少 family_id'}), 400

    db = get_db()

    # 检查家庭是否存在
    family = db.execute(
        'SELECT * FROM families WHERE family_id = ?', (family_id,)
    ).fetchone()
    if not family:
        db.close()
        return jsonify({'code': 404, 'message': '家庭不存在'}), 404

    # 删除所有关联记录
    tables = ['feeding', 'sleep', 'diaper', 'growth', 'vaccination', 'medication', 'notes']
    deleted_records = 0
    for t in tables:
        # 先统计
        row = db.execute(f'SELECT COUNT(*) as cnt FROM {t} WHERE family_id = ?', (family_id,)).fetchone()
        deleted_records += row['cnt']
        db.execute(f'DELETE FROM {t} WHERE family_id = ?', (family_id,))

    # 删除家庭成员
    db.execute('DELETE FROM family_members WHERE family_id = ?', (family_id,))

    # 删除家庭本身
    db.execute('DELETE FROM families WHERE family_id = ?', (family_id,))

    db.commit()
    db.close()

    return jsonify({
        'code': 0,
        'message': f'家庭 {family_id} 已删除',
        'data': {
            'family_id': family_id,
            'family_name': family['baby_name'],
            'deleted_records': deleted_records
        }
    })


# ==================== 用户管理 ====================

@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def list_users():
    """用户列表"""
    db = get_db()

    users = db.execute('''
        SELECT id, openid, nickname, avatar_url, status, created_at
        FROM users
        ORDER BY created_at DESC
    ''').fetchall()

    result = []
    for u in users:
        user_dict = dict(u)
        # 查询该用户所在的家庭
        families = db.execute('''
            SELECT fm.family_id, fm.role, fm.joined_at,
                   f.baby_name
            FROM family_members fm
            LEFT JOIN families f ON fm.family_id = f.family_id
            WHERE fm.openid = ?
        ''', (u['openid'],)).fetchall()
        user_dict['families'] = [dict(f) for f in families]
        result.append(user_dict)

    db.close()
    return jsonify({'code': 0, 'data': result, 'total': len(result)})


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_status(user_id):
    """更新用户状态（active / disabled）"""
    data = request.get_json()
    status = data.get('status', '')

    if status not in ('active', 'disabled'):
        return jsonify({'code': 400, 'message': 'status 必须为 active 或 disabled'}), 400

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        db.close()
        return jsonify({'code': 404, 'message': '用户不存在'}), 404

    db.execute('UPDATE users SET status = ? WHERE id = ?', (status, user_id))
    db.commit()
    db.close()

    return jsonify({
        'code': 0,
        'message': f'用户 {user_id} 状态已更新为 {status}',
        'data': {'id': user_id, 'status': status}
    })


# ==================== 记录列表 ====================

@admin_bp.route('/api/admin/records', methods=['GET'])
@admin_required
def list_records():
    """记录列表，支持 ?type=feeding&limit=50"""
    record_type = request.args.get('type', 'all')
    limit = request.args.get('limit', '50')
    try:
        limit = int(limit)
        limit = max(1, min(limit, 500))
    except:
        limit = 50

    db = get_db()

    # 所有记录类型映射
    record_tables = {
        'feeding': ('feeding', 'start_time'),
        'sleep': ('sleep', 'start_time'),
        'diaper': ('diaper', 'time'),
        'growth': ('growth', 'record_date'),
        'vaccination': ('vaccination', 'scheduled_date'),
        'medication': ('medication', 'start_time'),
        'notes': ('notes', 'time'),
    }

    if record_type == 'all':
        tables_to_query = list(record_tables.values())
    elif record_type in record_tables:
        tables_to_query = [record_tables[record_type]]
    else:
        db.close()
        return jsonify({
            'code': 400,
            'message': f'无效的 type 参数，可选: all, {", ".join(record_tables.keys())}'
        }), 400

    all_records = []
    for table_name, time_col in tables_to_query:
        rows = db.execute(
            f'SELECT *, "{table_name}" as _type FROM {table_name} '
            f'ORDER BY {time_col} DESC LIMIT ?',
            (limit,)
        ).fetchall()
        for r in rows:
            d = dict(r)
            d['type'] = d.pop('_type')
            all_records.append(d)

    # 按时间排序并截取
    def get_ts(r):
        return (r.get('start_time') or r.get('time') or
                r.get('record_date') or r.get('scheduled_date') or '')

    all_records.sort(key=get_ts, reverse=True)
    all_records = all_records[:limit]

    db.close()
    return jsonify({'code': 0, 'data': all_records, 'total': len(all_records)})