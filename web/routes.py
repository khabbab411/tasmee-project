from flask import render_template

def register_routes(app):

    @app.route("/")
    def login():
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard():
        return """
        <h2 style='text-align:center;margin-top:60px;font-family:Tahoma'>
        مرحبًا بك في لوحة مقرأة زاد الفرقان
        </h2>
        """
