from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)

app = Flask(__name__)

# ---------------- JWT CONFIG ----------------
app.config["JWT_SECRET_KEY"] = "super-secret-key"
jwt = JWTManager(app)

# ---------------- DATABASE ----------------
engine = create_engine(
    "postgresql://sanchit:YOUR_PASSWORD@localhost:5432/bank"
)

# ---------------- HOME ----------------
from flask import render_template

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/login-page")
def login_page():
    return render_template("login.html")
# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():

    data = request.json

    username = data["username"]
    password = data["password"]

    with engine.connect() as conn:

        result = conn.execute(
            text("""
                SELECT id, password
                FROM customer
                WHERE username = :username
            """),
            {"username": username}
        )

        user = result.fetchone()

        if user is None:
            return jsonify({"error": "Invalid username"}), 401

        if password != user.password:
            return jsonify({"error": "Invalid password"}), 401

        access_token = create_access_token(identity=str(user.id))

        return jsonify({"access_token": access_token}), 200


# ---------------- DEPOSIT ----------------
@app.route("/deposit", methods=["POST"])
@jwt_required()
def deposit():
    data = request.json

    
    amount = data["amount"]

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400
    user_id = get_jwt_identity()
    with engine.begin() as conn:

        conn.execute(
            text("""
                UPDATE customer
                SET balance = balance + :amount
                WHERE id = :id
            """),
            {"amount": amount, "id": user_id}
        )

    return jsonify({
        "message": "Deposit successful",
        "amount": amount
    }), 200


# ---------------- WITHDRAW ----------------
@app.route("/withdraw", methods=["POST"])
@jwt_required()
def withdraw():
    data = request.json

    
    amount = data["amount"]

    user_id = get_jwt_identity()
    with engine.begin() as conn:

        balance = conn.execute(
            text("SELECT balance FROM customer WHERE id = :id"),
            {"id": user_id}
        ).scalar()

        if balance is None:
            return jsonify({"error": "User not found"}), 404

        if amount <= 0:
            return jsonify({"error": "Enter positive amount"}), 400

        if amount > balance:
            return jsonify({"error": "No sufficient funds"}), 400

        conn.execute(
            text("""
                UPDATE customer
                SET balance = balance - :amount
                WHERE id = :id
            """),
            {"amount": amount, "id": user_id}
        )

        conn.execute(
            text("""
                INSERT INTO transactions (customer_id, amount, txn_type)
                VALUES (:id, :amount, :type)
            """),
            {
                "id": user_id,
                "amount": amount,
                "type": "withdraw"
            }
        )

    return jsonify({
        "message": "Withdraw successful",
        "amount": amount
    }), 200


# ---------------- TRANSFER ----------------
@app.route("/transfer", methods=["POST"])
@jwt_required()
def transfer_money():

    data = request.json

    sender_id = get_jwt_identity()
    receiver_id = data["receiver_id"]
    amount = data["amount"]

    with engine.begin() as conn:

        balance = conn.execute(
            text("SELECT balance FROM customer WHERE id = :id"),
            {"id": sender_id}
        ).scalar()

        if balance is None:
            return jsonify({"error": "Sender not found"}), 404

        if amount <= 0:
            return jsonify({"error": "Invalid amount"}), 400

        if amount > balance:
            return jsonify({"error": "Insufficient funds"}), 400

        receiver = conn.execute(
            text("SELECT id FROM customer WHERE id = :id"),
            {"id": receiver_id}
        ).scalar()

        if receiver is None:
            return jsonify({"error": "Receiver not found"}), 404

        conn.execute(
            text("""
                UPDATE customer
                SET balance = balance - :amount
                WHERE id = :id
            """),
            {"amount": amount, "id": sender_id}
        )

        conn.execute(
            text("""
                UPDATE customer
                SET balance = balance + :amount
                WHERE id = :id
            """),
            {"amount": amount, "id": receiver_id}
        )

        reference_id = f"TXN{sender_id}{receiver_id}{amount}"

        conn.execute(
            text("""
                INSERT INTO transactions(reference_id, customer_id, amount, txn_type)
                VALUES(:ref,:id,:amount,:type)
            """),
            {
                "ref": reference_id,
                "id": sender_id,
                "amount": -amount,
                "type": "transfer_sent"
            }
        )

        conn.execute(
            text("""
                INSERT INTO transactions(reference_id, customer_id, amount, txn_type)
                VALUES(:ref,:id,:amount,:type)
            """),
            {
                "ref": reference_id,
                "id": receiver_id,
                "amount": amount,
                "type": "transfer_received"
            }
        )

    return jsonify({
        "message": "Transfer Successful",
        "reference_id": reference_id,
        "amount": amount
    }), 200

# ---------------- CHECK BALANCE ----------------
@app.route("/check_balance", methods=["GET"])
@jwt_required()
def check_balance():

    user_id = get_jwt_identity()

    with engine.connect() as conn:

        balance = conn.execute(
            text("""
                SELECT balance
                FROM customer
                WHERE id = :id
            """),
            {"id": user_id}
        ).scalar()

    return jsonify({

        "customer_id": user_id,
        "balance": balance

    }), 200
# ---------------- TRANSACTIONS ----------------
@app.route("/transactions", methods=["GET"])
@jwt_required()
def get_transactions():

    user_id = get_jwt_identity()

    with engine.connect() as conn:

        result = conn.execute(
            text("""
                SELECT txn_id, amount, txn_type
                FROM transactions
                WHERE customer_id = :id
                ORDER BY txn_id DESC
            """),
            {"id": user_id}
        )

        rows = result.fetchall()

        transactions = []

        for row in rows:
            transactions.append({
                "txn_id": row.txn_id,
                "amount": row.amount,
                "txn_type": row.txn_type
            })

    return jsonify(transactions), 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)