"""BabyCare 育儿助手 - Flask 主入口 (v1.1)"""
import logging
from flask import Flask, jsonify
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化 SQLite 数据库
    import database  # noqa: F401 - 模块加载时自动建表

    # 注册蓝图
    from routes.feeding import feeding_bp
    from routes.sleep import sleep_bp
    from routes.diaper import diaper_bp
    from routes.ai import ai_bp
    from routes.analysis import analysis_bp
    from routes.growth import growth_bp
    from routes.vaccination import vaccination_bp
    from routes.medication import medication_bp

    app.register_blueprint(feeding_bp)
    app.register_blueprint(sleep_bp)
    app.register_blueprint(diaper_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(vaccination_bp)
    app.register_blueprint(medication_bp)

    # 健康检查
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "babycare-backend"})

    # 错误处理
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"code": 404, "message": "接口不存在"}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    logger.info(f"BabyCare Backend starting on port {Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
