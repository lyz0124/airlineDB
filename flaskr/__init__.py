from flask import Flask

from .routes.agent import bp as agent_bp
from .routes.auth import bp as auth_bp
from .routes.customer import bp as customer_bp
from .routes.dashboard import bp as dashboard_bp
from .routes.public import bp as public_bp
from .routes.staff import bp as staff_bp


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY="dev-secret-key")

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(staff_bp)

    return app
